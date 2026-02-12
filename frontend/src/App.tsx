import { BrowserRouter } from "react-router-dom";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import { AuthProvider } from "@/context/AuthContext";
import { AppRoutes } from "@/routes";

const App = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
