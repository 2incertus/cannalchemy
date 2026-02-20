import { BrowserRouter, Routes, Route } from "react-router-dom";
import Nav from "./components/Nav";
import Landing from "./pages/Landing";
import Explorer from "./pages/Explorer";
import StrainDetail from "./pages/StrainDetail";
import Compare from "./pages/Compare";
import Graph from "./pages/Graph";
import Quality from "./pages/Quality";

export default function App() {
  return (
    <BrowserRouter>
      <div className="grain-overlay" />
      <Nav />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/explore" element={<Explorer />} />
        <Route path="/strain/:name" element={<StrainDetail />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/quality" element={<Quality />} />
      </Routes>
    </BrowserRouter>
  );
}
