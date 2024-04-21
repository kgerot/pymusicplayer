import warnings

class pcol:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def _fmt(message, category, filename, lineno, line=''):
        return "{0} ({1}): {2}\n".format(category.__name__, lineno, message)

warnings.formatwarning = _fmt

def warning(message, category=Warning, col=pcol.WARNING):
    warnings.warn(f"{col}{message}{pcol.ENDC}", category=category, stacklevel=2)