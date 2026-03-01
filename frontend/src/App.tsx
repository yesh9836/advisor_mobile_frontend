import { BrowserRouter } from "react-router-dom";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import { AuthProvider } from "@/context/AuthContext";
import { APP_BASE_PATH } from "@/lib/app-path";
import { AppRoutes } from "@/routes";

const App = () => {
  return (
    <AuthProvider>
      <BrowserRouter basename={APP_BASE_PATH === "/" ? undefined : APP_BASE_PATH}>
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
