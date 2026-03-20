/**
 * @deprecated Watch SSE는 watchStream.ts로 이전됨. import는 @/lib/api/watchStream 사용.
 */
export {
  subscribeWatchStream,
  disconnectWatchStream,
  type WatchStreamCallbacks,
} from './watchStream';
