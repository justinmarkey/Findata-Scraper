"""Cloud digest runner: private S3 state, Gmail SMTP, durable per-edition receipts.

Never needs the desktop app or Gmail browser. Credentials come only from environment.
A pending delivery receipt stops automatic retry after an ambiguous network failure.
"""
import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid
import json
import os
from pathlib import Path
import smtplib
import ssl
import tarfile
import tempfile

from .reporting import build_report, mark_delivered
from .settings import load_settings
from .store import Lake


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ValueError(f'Missing required environment variable: {name}')
    return value


def pack_state(data_dir, archive):
    data_dir, archive = Path(data_dir).resolve(), Path(archive).resolve()
    if not (data_dir / 'lake/manifest.sqlite3').is_file():
        raise ValueError('Build the data lake before uploading cloud state')
    import sqlite3
    # Snapshot SQLite indexes consistently even if another local process has them open.
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        with tarfile.open(archive, 'w:gz') as bundle:
            for root in [data_dir / 'lake']:
                paths = [root] if root.is_file() else sorted(p for p in root.rglob('*') if p.is_file())
                for path in paths:
                    if path.is_symlink() or '.query-temp' in path.parts or path.name.startswith('.partial-'):
                        continue
                    if path.suffix == '.sqlite3':
                        copied = temporary / (str(len(list(temporary.iterdir()))) + '.sqlite3')
                        source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
                        destination = sqlite3.connect(copied)
                        try:
                            source.backup(destination)
                        finally:
                            source.close()
                            destination.close()
                        bundle.add(copied, arcname=str(path.relative_to(data_dir)), recursive=False)
                    else:
                        bundle.add(path, arcname=str(path.relative_to(data_dir)), recursive=False)


def unpack_state(archive, data_dir):
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as bundle:
        for member in bundle.getmembers():
            target = (data_dir / member.name).resolve()
            if not target.is_relative_to(data_dir) or not member.isfile():
                raise ValueError('State archive contains an unsafe path or non-file entry')
        # The validation above also supports Python 3.11 without filter='data'.
        bundle.extractall(data_dir, filter='data')


def smtp_send(message):
    username = required('SMTP_USERNAME')
    password = required('SMTP_PASSWORD')
    settings = load_settings()['cloud']
    host = os.environ.get('SMTP_HOST') or settings['smtp_host']
    port = int(os.environ.get('SMTP_PORT') or settings['smtp_port'])
    email = EmailMessage()
    email['From'] = username
    email['To'] = message['to']
    email['Subject'] = message['subject']
    email['Message-ID'] = make_msgid(domain='findata.local')
    email.set_content(message['text'])
    email.add_alternative(message['html'], subtype='html')
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=60) as smtp:
        smtp.login(username, password)
        refused = smtp.send_message(email)
        if refused:
            raise RuntimeError('SMTP server refused the recipient')
    # This is the RFC Message-ID acknowledged by SMTP, not a Gmail API message ID.
    return email['Message-ID']


def client():
    import boto3
    return boto3.client('s3', endpoint_url=os.environ.get('S3_ENDPOINT_URL') or None,
                        region_name=os.environ.get('AWS_DEFAULT_REGION') or load_settings()['cloud']['region'])


def claim_delivery(s3, bucket, key, message):
    from botocore.exceptions import ClientError
    receipt = {'status': 'pending', 'recipient': message['to'], 'subject': message['subject'],
               'delivery_id': message['delivery_id'], 'started_at': datetime.now(timezone.utc).isoformat()}
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(receipt).encode(),
                      ContentType='application/json', IfNoneMatch='*')
        return receipt
    except ClientError as exc:
        if exc.response.get('Error', {}).get('Code') in ('PreconditionFailed', '412', 'ConditionalRequestConflict'):
            return None
        raise


def run(data_dir, *, seed=False, dry_run=False):
    settings = load_settings()
    data_dir = Path(data_dir).resolve()
    bucket = required('FINDATA_S3_BUCKET')
    state_key = os.environ.get('FINDATA_STATE_KEY') or settings['cloud']['state_key']
    s3 = client()
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / 'state.tar.gz'
        if seed:
            pack_state(data_dir, archive)
            s3.upload_file(str(archive), bucket, state_key)
            return {'status': 'seeded'}
        required('REPORT_TO')
        s3.download_file(bucket, state_key, str(archive))
        unpack_state(archive, data_dir)
        lake = Lake(data_dir / 'lake')
        message_path = build_report(lake, refresh=True,
                                    output=data_dir / 'reports/cloud-digest', delivery_scope='session')
        message = json.loads(message_path.read_text())
        if dry_run:
            return {'status': 'preview', 'message': str(message_path)}
        # Check configuration before reserving this edition, so missing credentials can be fixed/retried.
        required('SMTP_USERNAME')
        required('SMTP_PASSWORD')
        # Persist refreshed data before reserving/sending; failures here are safe to retry.
        pack_state(data_dir, archive)
        s3.upload_file(str(archive), bucket, state_key)
        receipt_key = f'{settings["cloud"]["receipt_prefix"]}/{message["delivery_id"]}.json'
        receipt = claim_delivery(s3, bucket, receipt_key, message)
        if receipt is None:
            existing = json.loads(s3.get_object(Bucket=bucket, Key=receipt_key)['Body'].read())
            if existing['status'] == 'sent':
                return {'status': 'already_sent', 'message_id': existing['message_id']}
            raise RuntimeError('This edition has a pending delivery receipt. Inspect mail/provider logs before retrying to avoid duplicates.')
        message_id = smtp_send(message)
        receipt.update(status='sent', message_id=message_id,
                       accepted_at=datetime.now(timezone.utc).isoformat())
        s3.put_object(Bucket=bucket, Key=receipt_key, Body=json.dumps(receipt).encode(), ContentType='application/json')
        mark_delivered(lake, message_path, message_id, provider='smtp')
        pack_state(data_dir, archive)
        s3.upload_file(str(archive), bucket, state_key)
        return {'status': 'smtp_accepted', 'message_id': message_id}


def main():
    parser = argparse.ArgumentParser(description='Cloud screener digest runner')
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--seed', action='store_true', help='Upload existing local data as the initial private cloud state')
    parser.add_argument('--dry-run', action='store_true', help='Build preview without sending or claiming an edition')
    args = parser.parse_args()
    print(json.dumps(run(args.data_dir, seed=args.seed, dry_run=args.dry_run)))


if __name__ == '__main__':
    main()
