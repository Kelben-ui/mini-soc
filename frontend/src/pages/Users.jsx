import { useEffect, useState } from "react";
import { getRole } from "../api/auth";
import {
  createUser,
  getUsers,
  resetUserPassword,
  updateUserRole,
} from "../api/users";

const ROLES = ["analyst", "lead", "admin"];
const MIN_PASSWORD_LENGTH = 12;

export default function Users() {
  const role = getRole();
  const isAdmin = role === "admin";

  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("analyst");

  const [resetTarget, setResetTarget] = useState(null);
  const [resetPassword, setResetPassword] = useState("");

  function load() {
    return getUsers()
      .then((res) => setUsers(Array.isArray(res.data) ? res.data : []))
      .catch(() => setError("Could not load users."));
  }

  useEffect(() => {
    load();
  }, []);

  function flash(message) {
    setNotice(message);
    setError("");
  }

  async function handleCreate(event) {
    event.preventDefault();
    setBusy(true);

    try {
      await createUser({
        username: newUsername,
        password: newPassword,
        role: newRole,
      });
      setNewUsername("");
      setNewPassword("");
      setNewRole("analyst");
      await load();
      flash("User created.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not create the user.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRoleChange(user, nextRole) {
    setBusy(true);

    try {
      await updateUserRole(user.id, nextRole);
      await load();
      flash(`${user.username} is now ${nextRole}.`);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not change the role.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResetPassword(event) {
    event.preventDefault();
    if (!resetTarget) return;

    setBusy(true);

    try {
      await resetUserPassword(resetTarget.id, resetPassword);
      setResetTarget(null);
      setResetPassword("");
      flash("Password updated.");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not reset the password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Users</h1>

      {notice && (
        <p className="rounded border border-emerald-900 bg-emerald-950 px-3 py-2 text-sm text-emerald-300">
          {notice}
        </p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {isAdmin && (
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Create user
          </h2>
          <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
            <input
              value={newUsername}
              onChange={(event) => setNewUsername(event.target.value)}
              placeholder="username"
              required
              minLength={3}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder={`password (min ${MIN_PASSWORD_LENGTH})`}
              required
              minLength={MIN_PASSWORD_LENGTH}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <select
              value={newRole}
              onChange={(event) => setNewRole(event.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            >
              {ROLES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
            >
              Create
            </button>
          </form>
        </section>
      )}

      <section className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-2">ID</th>
              <th className="px-4 py-2">Username</th>
              <th className="px-4 py-2">Role</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {users.length === 0 ? (
              <tr>
                <td colSpan="4" className="px-4 py-8 text-center text-slate-500">
                  No users.
                </td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id} className="hover:bg-slate-900/60">
                  <td className="px-4 py-2 text-slate-400">{user.id}</td>
                  <td className="px-4 py-2">{user.username}</td>
                  <td className="px-4 py-2">
                    {isAdmin ? (
                      <select
                        value={user.role}
                        onChange={(event) =>
                          handleRoleChange(user, event.target.value)
                        }
                        disabled={busy}
                        className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
                      >
                        {ROLES.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="uppercase text-slate-300">{user.role}</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    {isAdmin && (
                      <button
                        type="button"
                        onClick={() => setResetTarget(user)}
                        className="rounded bg-slate-800 px-3 py-1 text-xs font-semibold hover:bg-slate-700"
                      >
                        Reset password
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      {resetTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <form
            onSubmit={handleResetPassword}
            className="w-full max-w-md space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-5"
          >
            <h2 className="text-lg font-semibold">
              Reset password for {resetTarget.username}
            </h2>
            <input
              type="password"
              value={resetPassword}
              onChange={(event) => setResetPassword(event.target.value)}
              placeholder={`New password (min ${MIN_PASSWORD_LENGTH})`}
              required
              minLength={MIN_PASSWORD_LENGTH}
              className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  setResetTarget(null);
                  setResetPassword("");
                }}
                className="rounded border border-slate-700 px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy}
                className="rounded bg-sky-700 px-4 py-2 text-sm font-semibold hover:bg-sky-600 disabled:opacity-40"
              >
                Save
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
