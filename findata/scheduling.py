"""Keep the checked-in cloud schedule consistent with the public settings file."""
from datetime import time


def schedule_entries(settings):
    report = settings['reports']
    entries = []
    for field in ['morning_time', 'evening_time']:
        stamp = time.fromisoformat(report[field])
        entries.append({'cron': f'{stamp.minute} {stamp.hour} * * *', 'timezone': report['timezone']})
    return entries


def sync_schedule(settings, path):
    from pathlib import Path
    path = Path(path)
    begin, end = '    # BEGIN CONFIGURED SCHEDULE', '    # END CONFIGURED SCHEDULE'
    text = path.read_text()
    if begin not in text or end not in text:
        raise ValueError('Workflow is missing configured-schedule markers')
    before, rest = text.split(begin, 1)
    _, after = rest.split(end, 1)
    lines = [begin]
    for entry in schedule_entries(settings):
        lines += [f"    - cron: '{entry['cron']}'", f"      timezone: {entry['timezone']}"]
    path.write_text(before + '\n'.join(lines) + '\n' + end + after)
