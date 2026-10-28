import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import Dashboard from "./pages/Dashboard";
import Empreendimentos from "./pages/Empreendimentos";
import Torres from "./pages/Torres";
import Unidades from "./pages/Unidades";
import ImportExcel from "./pages/ImportExcel";
import "./index.css";

const qc = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="empreendimentos" element={<Empreendimentos />} />
            <Route path="torres" element={<Torres />} />
            <Route path="unidades" element={<Unidades />} />
            <Route path="importar" element={<ImportExcel />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
