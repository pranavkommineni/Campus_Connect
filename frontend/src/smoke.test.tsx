import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Login } from "./pages/Auth";
import { AuthProvider } from "./auth";
import { ToastProvider, Badge } from "./ui";
import { fmt, toLocalInput } from "./api";

test("login form renders accessible fields", () => {
  render(<MemoryRouter><ToastProvider><AuthProvider><Login /></AuthProvider></ToastProvider></MemoryRouter>);
  expect(screen.getByText("Email")).toBeTruthy();
  expect(screen.getByRole("button", { name: /log in/i })).toBeTruthy();
});
test("status badge humanises status", () => {
  render(<Badge s="pending_approval" />);
  expect(screen.getByText("pending approval")).toBeTruthy();
});
test("date helpers", () => {
  expect(toLocalInput("")).toBe("");
  expect(fmt("2030-01-01T10:00:00Z")).toContain("2030");
});
