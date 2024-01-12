import asyncio
import json
import typing
from fastapi import FastAPI
from socketio import AsyncServer

MessagePayload = typing.Any
ActiveConnections = typing.Dict[str, typing.Set[AsyncServer]]


class SocketIOManager:
    _connected = 0
    _connection_limit = 0
    _protocol_table = {}
    _socket_serial = 0
    SERIAL_MAX = 0XFFFFFFFF
    _socket_pool = {}
    _socket_events = set()

    def __init__(self) -> None:
        self.active_connections: ActiveConnections = {}
        self.sio = AsyncServer()

    @classmethod
    def set_connection_limit(cls, limit: int = 0) -> None:
        cls._connection_limit = max(0, limit)

    @classmethod
    def get_socket_ids(cls) -> typing.Tuple[int, ...]:
        return tuple(cls._socket_pool.keys())

    @classmethod
    def add_protocol(cls, protocol: str, func: typing.Callable) -> None:
        cls._protocol_table[protocol] = func

    @classmethod
    def add_socket_event(cls, func: typing.Callable) -> None:
        cls._socket_events.add(func)

    @classmethod
    def clear_socket_event(cls) -> None:
        cls._socket_events.clear()

    @classmethod
    async def broadcast(cls, data) -> typing.Awaitable:
        emit_cor_list = [sio.emit('message', data, room=socket_id) for socket_id, sio in cls._socket_pool.items()]
        return asyncio.gather(*emit_cor_list, return_exceptions=True)

    @classmethod
    async def multicast(cls, data, socket_ids: typing.Optional[typing.Iterable[int]] = None) -> typing.Awaitable:
        socket_ids = set(socket_ids) if socket_ids else cls._socket_pool.keys()
        emit_cor_list = [cls._socket_pool[socket_id].emit('message', data, room=socket_id) for socket_id in socket_ids if socket_id in cls._socket_pool]
        return asyncio.gather(*emit_cor_list, return_exceptions=True)

    @classmethod
    def _append_socket(cls) -> int:
        cls._socket_serial = (cls._socket_serial % cls.SERIAL_MAX) + 1
        while cls._socket_serial in cls._socket_pool:
            cls._socket_serial = (cls._socket_serial % cls.SERIAL_MAX) + 1
        cls._socket_pool[cls._socket_serial] = cls.sio
        return cls._socket_serial

    @classmethod
    def _delete_socket(cls, socket_id: int) -> None:
        cls._socket_pool.pop(socket_id, None)

    async def on_connect(self, sid, environ):
        self._connected += 1
        socket_id = self._append_socket()
        await self.sio.emit('message', {'protocol': 'system', 'key': 'connect', 'id': 0,
                                         'data': socket_id if self._connection_limit <= 0 or self._connected <= self._connection_limit else None,
                                         'exception': 'Connection refused due to connection limit @python'}, room=sid)
        await self.sio.emit('message', {'protocol': 'system', 'key': 'connect', 'id': 0,
                                         'data': socket_id if self._connection_limit <= 0 or self._connected <= self._connection_limit else None,
                                         'exception': None}, room=sid)
        for callback in self._socket_events:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(socket_id, 'connect'))
                else:
                    callback(socket_id, 'connect')
            except Exception:
                pass

    async def on_receive(self, sid, data: str):
        try:
            dict_data = json.loads(data)
            if all(key in dict_data for key in ['protocol', 'key', 'id', 'data', 'exception']):
                call_func = self._protocol_table.get(dict_data['protocol'])
                if call_func and (asyncio.iscoroutinefunction(call_func)):
                    asyncio.create_task(call_func(self.sio, sid, dict_data))
                elif call_func:
                    call_func(self.sio, sid, dict_data)
        except Exception:
            pass

    async def on_disconnect(self, sid, close_code: int):
        self._delete_socket(sid)
        self._connected -= 1
        for callback in self._socket_events:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(sid, 'disconnect'))
                else:
                    callback(sid, 'disconnect')
            except Exception:
                pass
