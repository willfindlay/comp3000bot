import humanreadable as hr


def to_time(argument):
    try:
        time = hr.Time(argument, default_unit='minutes')
    except Exception:
        raise Exception(f'Unable to parse time from {argument}') from None
    return time.seconds
