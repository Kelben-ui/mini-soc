import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const getUsers = vi.fn();
const createUser = vi.fn();
const updateUserRole = vi.fn();
const resetUserPassword = vi.fn();
const deactivateUser = vi.fn();
const activateUser = vi.fn();

vi.mock("../api/users", () => ({
  getUsers: (...args) => getUsers(...args),
  createUser: (...args) => createUser(...args),
  updateUserRole: (...args) => updateUserRole(...args),
  resetUserPassword: (...args) => resetUserPassword(...args),
  deactivateUser: (...args) => deactivateUser(...args),
  activateUser: (...args) => activateUser(...args),
}));

vi.mock("../api/auth", () => ({
  getRole: () => "admin",
  getUserId: () => 1,
}));

import Users from "../pages/Users";

const USERS = [
  { id: 1, username: "admin", role: "admin", is_active: true },
  { id: 2, username: "analyst", role: "analyst", is_active: true },
  { id: 3, username: "ghost", role: "analyst", is_active: false },
];

describe("Users", () => {
  beforeEach(() => {
    getUsers.mockReset();
    deactivateUser.mockReset();
    activateUser.mockReset();
    getUsers.mockResolvedValue({ data: USERS });
    deactivateUser.mockResolvedValue({ data: { ...USERS[1], is_active: false } });
  });

  it("shows the active/inactive status of each user", async () => {
    render(<Users />);

    expect(await screen.findByText("ghost")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("disables deactivation for your own account", async () => {
    render(<Users />);
    await screen.findByText("admin");

    const selfDeactivate = screen
      .getAllByRole("button", { name: /^deactivate$/i })
      .find((button) => button.disabled);

    expect(selfDeactivate).toBeDefined();
  });

  it("deactivates another user after confirmation", async () => {
    render(<Users />);
    await screen.findByText("analyst");

    const rowButton = screen
      .getAllByRole("button", { name: /^deactivate$/i })
      .find((button) => !button.disabled);

    await userEvent.click(rowButton);

    const dialog = await screen.findByRole("dialog", {
      name: /deactivate user/i,
    });

    await userEvent.click(
      within(dialog).getByRole("button", { name: /^deactivate$/i })
    );

    await waitFor(() => expect(deactivateUser).toHaveBeenCalledWith(2));
  });
});
