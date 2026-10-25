"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("agentscope-theme");
    const enabled = saved ? saved === "dark" : true;
    document.documentElement.classList.toggle("dark", enabled);
    setDark(enabled);
  }, []);

  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("agentscope-theme", next ? "dark" : "light");
    setDark(next);
  }

  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="flex items-center gap-2 rounded-xl border border-[#555b6b]/40 px-4 py-2.5 text-sm font-medium transition hover:opacity-75"
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
      {dark ? "Light mode" : "Dark mode"}
    </button>
  );
}
