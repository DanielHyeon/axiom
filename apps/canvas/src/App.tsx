import React from 'react';
import { Toaster } from 'sonner';
import { RouterProvider } from 'react-router-dom';
import { GlobalErrorBoundary } from './components/GlobalErrorBoundary';
import { WatchToastListener } from './features/watch/components/WatchToastListener';
import { router } from './lib/routes/routeConfig';

export const App: React.FC = () => {
  return (
    <GlobalErrorBoundary>
      <Toaster richColors position="top-right" />
      <WatchToastListener />
      <RouterProvider router={router} />
    </GlobalErrorBoundary>
  );
};

export default App;
