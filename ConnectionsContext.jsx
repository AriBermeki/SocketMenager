import React, { createContext, useContext, useEffect, useState, useMemo } from 'react';
import io from 'socket.io-client';

const JsPyTextSocketContext = createContext();

const JsPyTextSocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null);
  const [url, setUrl] = useState('ws://localhost:8000');
  const [socketId, setSocketId] = useState(null);
  const [disconnectReason, setDisconnectReason] = useState('It has not been initialized yet.');
  const [protocol_table, setProtocolTable] = useState(new Map());
  const [socket_events, setSocketEvents] = useState([]);


  useEffect(() => {
    const query = { 'client_id': '5555' };
    const extraHeaders = {};
    const transports = ['websocket', 'polling'];

    const newSocket = io(url, { path: "/nexium/socket.io", query, extraHeaders, transports });

    setSocket(newSocket);

    newSocket.on('message', (event) => {
      try {
        let msg_obj = JSON.parse(event);
        if ('protocol' in msg_obj && 'key' in msg_obj && 'id' in msg_obj &&
          'data' in msg_obj && 'exception' in msg_obj && protocol_table.has(msg_obj['protocol'])) {
          protocol_table.get(msg_obj['protocol'])(msg_obj);
        }
      } catch (e) {
        console.error(e); // Log the error for debugging purposes
      }
    });

    newSocket.on('disconnect', (event) => {
      for (const fn of socket_events) {
        try {
          fn();
        } catch (e) {
          console.error(e); // Log the error for debugging purposes
        }
      }
      setSocketId(null);
    });

    return () => {
      newSocket.disconnect();
    };
  }, [url, protocol_table, socket_events]);

  const closeSocket = () => {
    socket.disconnect();
  };

  const isSocketReady = () => {
    return socket && socket.connected;
  };

  const sendJson = (sendObj) => {
    socket.emit('send_json', sendObj);
  };
  const initUrl = (new_url) => {
    return setUrl(new_url);
  };
  const getSocketId = () => {
    return socketId;
  };

  const addProtocol = (protocol, func) => {
    setProtocolTable(new Map(protocol_table.set(protocol, func)));
  };

  const addCloseEvent = (func) => {
    setSocketEvents([...socket_events, func]);
  };

  const clearCloseEvent = () => {
    setSocketEvents([]);
  };

  const handleSystemProtocol = (objData) => {
    if (objData['key'] === 'connect') {
      let data = objData['data'];
      let except = objData['exception'];
      if (except) {
        setSocketId(null);
        setDisconnectReason(except);
      } else {
        setSocketId(data);
        setDisconnectReason('');
      }
    }
  };

  useEffect(() => {
    addProtocol('system', handleSystemProtocol);

    return () => {
      setProtocolTable(new Map(protocol_table.delete('system')));
    };
  }, [protocol_table]);

    const contextValue = useMemo(() => ({
      initUrl,
      closeSocket,
      isSocketReady,
      sendJson,
      getSocketId,
      addProtocol,
      addCloseEvent,
      clearCloseEvent,
      socketId,
      disconnectReason,
    }), []);

  return (
    <JsPyTextSocketContext.Provider value={contextValue}>
      {children}
    </JsPyTextSocketContext.Provider>
  );
};

const useJsPyTextSocket = () => {
  return useContext(JsPyTextSocketContext);
};

export { JsPyTextSocketProvider, useJsPyTextSocket };
