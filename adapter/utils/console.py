RESET   = "\033[0m"
BOLD    = "\033[1m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
DIM     = "\033[2m"
WHITE   = "\033[97m"


def color(text, *codes):
    return "".join(codes) + str(text) + RESET


def header(title):
    line = "=" * 60
    print(f"\n{color(line, CYAN)}")
    print(f"{color('  ' + title, CYAN, BOLD)}")
    print(f"{color(line, CYAN)}\n")


def section(title):
    print(f"\n{color('> ' + title, YELLOW, BOLD)}")
    print(color("-" * 50, DIM))


def success(msg): print(f"  {color('OK', GREEN, BOLD)}  {msg}")
def warn(msg):    print(f"  {color('!!', YELLOW, BOLD)}  {msg}")
def error(msg):   print(f"  {color('XX', RED, BOLD)}  {msg}")
def info(msg):    print(f"  {color('--', CYAN)}  {msg}")
