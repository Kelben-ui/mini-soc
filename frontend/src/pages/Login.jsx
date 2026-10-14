import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Login failed. Check your username and password.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4 text-slate-100">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-6"
      >
        <div>
          <h1 className="text-xl font-bold">Mini SOC Platform</h1>
          <p className="mt-1 text-sm text-slate-400">Analyst sign-in</p>
        </div>

        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Username"
          autoComplete="username"
          required
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder:text-slate-500"
        />

        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Password"
          autoComplete="current-password"
          required
          className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder:text-slate-500"
        />

        <button
          type="submit"
          className="w-full rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600"
        >
          Log in
        </button>

        {error && <p className="text-sm text-red-400">{error}</p>}
      </form>
    </div>
  );
}
