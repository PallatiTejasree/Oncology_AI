import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import api from "./services/api";

jest.mock("./services/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

beforeEach(() => {
  localStorage.clear();
  jest.clearAllMocks();
});

test("renders the dashboard with a dynamic clinical prompt and no voice control", async () => {
  localStorage.setItem("access_token", "test-token");
  localStorage.setItem("email", "tejasree@example.com");
  localStorage.setItem("user", JSON.stringify({ full_name: "Tejasree" }));
  api.get.mockImplementation((path) => {
    if (path === "/auth/me") {
      return Promise.resolve({
        data: { email: "tejasree@example.com", full_name: "Tejasree" },
      });
    }
    if (path === "/upload/history/tejasree@example.com") {
      return Promise.resolve({ data: [] });
    }
    return Promise.reject(new Error(`Unexpected GET ${path}`));
  });

  render(
    <MemoryRouter
      initialEntries={["/dashboard"]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <App />
    </MemoryRouter>
  );

  expect(await screen.findByText(/^Tejasree$/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/message to medical ai assistant/i)).toHaveAttribute("placeholder");
  expect(screen.queryByRole("button", { name: /voice/i })).not.toBeInTheDocument();
});
