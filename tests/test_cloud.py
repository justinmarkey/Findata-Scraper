import io
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from findata.cloud import claim_delivery, pack_state, smtp_send, unpack_state


class CloudTests(unittest.TestCase):
    def test_state_archive_roundtrip_and_safe_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / 'source'
            (data / 'lake').mkdir(parents=True)
            db = sqlite3.connect(data / 'lake/manifest.sqlite3')
            db.execute('CREATE TABLE example(value INTEGER)')
            db.execute('INSERT INTO example VALUES (42)')
            db.commit()
            db.close()
            (data / 'lake/raw').mkdir(parents=True)
            (data / 'lake/raw/example.json').write_text('{"value": 42}')
            pack_state(data, root / 'state.tar.gz')
            unpack_state(root / 'state.tar.gz', root / 'destination')
            db = sqlite3.connect(root / 'destination/lake/manifest.sqlite3')
            self.assertEqual(db.execute('SELECT value FROM example').fetchone()[0], 42)
            db.close()
            self.assertEqual((root / 'destination/lake/raw/example.json').read_text(), '{"value": 42}')
            with tarfile.open(root / 'bad.tar.gz', 'w:gz') as archive:
                item = tarfile.TarInfo('../outside')
                item.size = 1
                archive.addfile(item, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                unpack_state(root / 'bad.tar.gz', root / 'unsafe')

    def test_atomic_receipt_prevents_duplicate_delivery(self):
        from botocore.exceptions import ClientError
        s3 = Mock()
        message = {'to': 'justinsmarkey@gmail.com', 'subject': 'Digest', 'delivery_id': 'unique'}
        receipt = claim_delivery(s3, 'bucket', 'key', message)
        self.assertEqual(receipt['status'], 'pending')
        self.assertEqual(s3.put_object.call_args.kwargs['IfNoneMatch'], '*')
        s3.put_object.side_effect = ClientError({'Error': {'Code': 'PreconditionFailed'}}, 'PutObject')
        self.assertIsNone(claim_delivery(s3, 'bucket', 'key', message))
        s3.put_object.side_effect = ClientError({'Error': {'Code': 'AccessDenied'}}, 'PutObject')
        with self.assertRaises(ClientError):
            claim_delivery(s3, 'bucket', 'key', message)

    def test_smtp_uses_tls_and_message_alternatives(self):
        message = {'to': 'justinsmarkey@gmail.com', 'subject': 'Digest', 'text': 'Text', 'html': '<p>HTML</p>'}
        session = Mock()
        session.send_message.return_value = {}
        with patch.dict(os.environ, {'SMTP_USERNAME': 'sender@example.com', 'SMTP_PASSWORD': 'test-secret'}):
            with patch('findata.cloud.smtplib.SMTP_SSL') as factory:
                factory.return_value.__enter__.return_value = session
                accepted_id = smtp_send(message)
                self.assertIn('findata.local', accepted_id)
                self.assertEqual(factory.call_args.args, ('smtp.gmail.com', 465))
                sent = session.send_message.call_args.args[0]
                self.assertEqual(sent['To'], 'justinsmarkey@gmail.com')
                self.assertTrue(sent.is_multipart())


if __name__ == '__main__':
    unittest.main()
