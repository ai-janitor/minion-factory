import { useState } from "react"
import Dashboard from "./components/Dashboard"
import LoginPage from "./components/LoginPage"

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("token"))

  if (!token) {
    return <LoginPage onLogin={setToken} />
  }

  return <Dashboard />
}

export default App
