export const fetcher = (url: string) => {
  const token = localStorage.getItem("token")
  const headers: HeadersInit = {}
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }
  return fetch(url, { headers }).then(r => {
    if (r.status === 401) {
      localStorage.removeItem("token")
      window.location.reload()
      throw new Error("Unauthorized")
    }
    if (!r.ok) {
      throw new Error(`HTTP ${r.status}`)
    }
    return r.json()
  })
}
