import socket, time

# replacement for python 2's mimetools.choose_boundary()
# from https://github.com/enthought/Python-2.7.3/blob/master/Lib/mimetools.py
# https://hg.python.org/cpython/file/41ea764e8321/Lib/email/generator.py#l359

def choose_boundary():
    """Return a string usable as a multipart boundary.
    The string chosen is unique within a single program run, and
    incorporates the user id (if available), process id (if available),
    and current time.  So it's very unlikely the returned string appears
    in message text, but there's no guarantee.
    The boundary contains dots so you have to quote it in the header."""

    global _prefix
    import time
    if _prefix is None:
        import socket
        try:
            hostid = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            hostid = '127.0.0.1'
        try:
            uid = repr(os.getuid())
        except AttributeError:
            uid = '1'
        try:
            pid = repr(os.getpid())
        except AttributeError:
            pid = '1'
        _prefix = hostid + '.' + uid + '.' + pid
    return "%s.%.3f.%d" % (_prefix, time.time(), _get_next_counter())