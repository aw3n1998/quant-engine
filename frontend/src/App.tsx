import Dashboard from "./pages/Dashboard";

function App() {
  return (
    <div className="min-h-screen p-4 md:p-8 flex flex-col">
      <main className="flex-1 w-full max-w-[1600px] mx-auto mt-4">
        <Dashboard />
      </main>
    </div>
  );
}

export default App;
