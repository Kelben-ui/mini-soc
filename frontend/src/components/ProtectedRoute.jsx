import { Navigate } from "react-router-dom";

export default function ProtectedRoute({ children }) {
  const token = localStorage.getItem("jwt");
  return token ? children : <Navigate to="/login" replace />;
}
