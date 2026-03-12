import { useEffect, useRef, useState, useCallback } from 'react';
import { createWebSocketUrl } from '../api/client';
import type { StageUpdate } from '../types/pipeline';

const MAX_RETRIES = 3;
const RETRY_DELAY = 2000;

export function useWebSocket(
  pipelineId: string | null,
  onUpdate: (update: StageUpdate) => void,
) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    retriesRef.current = 0;
  }, []);

  useEffect(() => {
    if (!pipelineId) return;

    function connect() {
      const url = createWebSocketUrl(pipelineId!);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log(`[WS] Connected to ${pipelineId}`);
        setIsConnected(true);
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data: StageUpdate = JSON.parse(event.data);
          console.log('[WS] Message:', data);
          onUpdateRef.current(data);
        } catch (err) {
          console.warn('[WS] Failed to parse message:', event.data);
        }
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected');
        setIsConnected(false);
        wsRef.current = null;

        if (retriesRef.current < MAX_RETRIES) {
          retriesRef.current++;
          console.log(`[WS] Retrying (${retriesRef.current}/${MAX_RETRIES})...`);
          setTimeout(connect, RETRY_DELAY);
        }
      };
    }

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [pipelineId]);

  return { isConnected, disconnect };
}
