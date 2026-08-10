import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

test("renders the dashboard with a dynamic clinical prompt and no voice control", () => {
  localStorage.setItem("user", JSON.stringify({ full_name: "Tejasree" }));

  render(
    <MemoryRouter
      initialEntries={["/dashboard"]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <App />
    </MemoryRouter>
  );

  expect(screen.getByText(/^Tejasree$/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/message to medical ai assistant/i)).toHaveAttribute("placeholder");
  expect(screen.queryByRole("button", { name: /voice/i })).not.toBeInTheDocument();
});
