from ctypes import (
    CDLL, CFUNCTYPE, POINTER, Union, Structure, memset, sizeof, byref, c_long,
    c_size_t, c_int64, c_short, c_int, c_uint, c_ulong, c_void_p, c_longlong,
    cast,
)
import sys

class timespec(Structure):
    _fields_ = [
        # XXX: is this the correct definition ?
        ('tv_sec', c_int64),
        ('tv_nsec', c_long),
    ]

class sockaddr(Structure):
    # XXX: not implemented !
    pass

class iovec(Structure):
    _fields_ = [
        ('iov_base', c_void_p),
        ('iov_len', c_size_t),
    ]

class io_context(Structure):
    pass
io_context_t = POINTER(io_context)
io_context_t_p = POINTER(io_context_t)

# io_iocb_cmd
IO_CMD_PREAD = 0
IO_CMD_PWRITE = 1
IO_CMD_FSYNC = 2
IO_CMD_FDSYNC = 3
#IO_CMD_POLL = 5 # Never implemented in mainline, see io_prep_poll
IO_CMD_NOOP = 6
IO_CMD_PREADV = 7
IO_CMD_PWRITEV = 8

PADDED, PADDEDptr, PADDEDul = {
    (4, 'little'): (
        lambda w, x, y: [(x, w), (y, c_uint)],
        lambda w, x, y: [(x, w), (y, c_uint)],
        lambda    x, y: [(x, c_ulong), (y, c_uint)],
    ),
    (8, 'little'): (
        lambda w, x, y: [(x, w), (y, w)],
        lambda w, x, _: [(x, w)],
        lambda    x, _: [(x, c_ulong)],
    ),
    (8, 'big'): (
        lambda w, x, y: [(y, c_uint), (x, w)],
        lambda w, x, _: [(x, w)],
        lambda    x, _: [(x, c_ulong)],
    ),
    (4, 'big'): (
        lambda w, x, y: [(y, c_uint), (x, w)],
        lambda w, x, y: [(y, c_uint), (x, w)],
        lambda    x, y: [(y, c_uint), (x, c_ulong)],
    ),
}[(sizeof(c_ulong), sys.byteorder)]

class io_iocb_poll(Structure):
    _fields_ = PADDED(c_int, 'events', '__pad1')

class io_iocb_sockaddr(Structure):
    _fields_ = [
        ('addr', POINTER(sockaddr)),
        ('len', c_int),
    ]

class io_iocb_common(Structure):
    _fields_ = (
        PADDEDptr(c_void_p, 'buf', '__pad1') +
        PADDEDul('nbytes', '__pad2') +
        [
            ('offset', c_longlong),
            ('__pad3', c_longlong),
            ('flags', c_uint),
            ('resfd', c_uint),
        ]
    )

class io_iocb_vector(Structure):
    _fields_ = [
        ('vec', POINTER(iovec)),
        ('nr', c_int),
        ('offset', c_longlong),
    ]

class _iocb_u(Union):
    _fields_ = [
        ('c', io_iocb_common),
        ('v', io_iocb_vector),
        ('poll', io_iocb_poll),
        ('saddr', io_iocb_sockaddr),
    ]

class iocb(Structure):
    _fields_ = (
        PADDEDptr(c_void_p, 'data', '__pad1') +
        PADDED(c_uint, 'key', '__pad2') +
        [
            ('aio_lio_opcode', c_short),
            ('aio_reqprio', c_short),
            ('aio_fildes', c_int),
            ('u', _iocb_u),
        ]
    )

del _iocb_u

iocb_p = POINTER(iocb)
iocb_pp = POINTER(iocb_p)

class io_event(Structure):
    _fields_ = (
        PADDEDptr(c_void_p, 'data', '__pad1') +
        PADDEDptr(iocb_p, 'obj', '__pad2') +
        PADDEDul('res', '__pad3') +
        PADDEDul('res2', '__pad4')
    )
io_event_p = POINTER(io_event)

del PADDED, PADDEDptr, PADDEDul

io_callback_t = CFUNCTYPE(None, io_context_t, iocb, c_long, c_long)

libaio = CDLL('libaio.so.1')
def _raise_on_negative(result, func, arguments):
    if result < 0:
        raise IOError(-result)
    return result

def _func(name, *args):
    result = getattr(libaio, name)
    result.restype = c_int
    result.argtypes = args
    result.errcheck = _raise_on_negative
    return result

io_queue_init = _func('io_queue_init', c_int, io_context_t_p)
io_queue_release = _func('io_queue_release', io_context_t)
io_queue_run = _func('io_queue_run', io_context_t)
io_setup = _func('io_setup', c_int, io_context_t_p)
io_destroy = _func('io_destroy', io_context_t)
io_submit = _func('io_submit', io_context_t, c_long, iocb_pp)
io_cancel = _func('io_cancel', io_context_t, iocb_p, io_event_p)
io_getevents = _func(
    'io_getevents',
    io_context_t,
    c_long,
    c_long,
    io_event_p,
    POINTER(timespec),
)

def io_set_callback(iocb, cb):
    iocb.data = cast(io_callback_t(cb), c_void_p)

def zero(struct):
    memset(byref(struct), 0, sizeof(struct))

def _io_prep_prw(opcode, iocb, fd, buf, count, offset):
    zero(iocb)
    iocb.aio_fildes = fd
    iocb.aio_lio_opcode = opcode
    iocb.aio_reqprio = 0
    iocb.u.c.buf = buf
    iocb.u.c.nbytes = count
    iocb.u.c.offset = offset

def io_prep_pread(iocb, fd, buf, count, offset):
    _io_prep_prw(IO_CMD_PREAD, iocb, fd, buf, count, offset)

def io_prep_pwrite(iocb, fd, buf, count, offset):
    _io_prep_prw(IO_CMD_PWRITE, iocb, fd, buf, count, offset)

def io_prep_preadv(iocb, fd, iov, iovcnt, offset):
    _io_prep_prw(IO_CMD_PREADV, iocb, fd, cast(iov, c_void_p), iovcnt, offset)

def io_prep_pwritev(iocb, fd, iov, iovcnt, offset):
    _io_prep_prw(IO_CMD_PWRITEV, iocb, fd, cast(iov, c_void_p), iovcnt, offset)

# io_prep_poll
# io_poll

def io_prep_fsync(iocb, fd):
    zero(iocb)
    iocb.aio_fildes = fd
    iocb.aio_lio_opcode = IO_CMD_FSYNC
    iocb.aio_reqprio = 0

def io_fsync(ctx, iocb, cb, fd):
    io_prep_fsync(iocb, fd)
    io_set_callback(iocb, cb)
    return io_submit(ctx, 1, iocb_pp(byref(iocb)))

def io_prep_fdsync(iocb, fd):
    zero(iocb)
    iocb.aio_fildes = fd
    iocb.aio_lio_opcode = IO_CMD_FDSYNC
    iocb.aio_reqprio = 0

def io_fdsync(ctx, iocb, cb, fd):
    io_prep_fdsync(iocb, fd)
    io_set_callback(iocb, cb)
    return io_submit(ctx, 1, iocb_pp(byref(iocb)))

IOCB_FLAG_RESFD = 1 << 0

def io_set_eventfd(iocb, eventfd):
    iocb.u.c.flags |= IOCB_FLAG_RESFD
    iocb.u.c.resfd = eventfd
