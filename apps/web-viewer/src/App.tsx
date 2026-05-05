import Routes from "./routes";
import Nav from "./components/Nav";

export default function App() {
  return (
    <div>
      <Nav />
      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "1.5rem" }}>
        <Routes />
      </main>
    </div>
  );
}
