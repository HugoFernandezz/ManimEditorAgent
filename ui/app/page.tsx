import { Video } from "lucide-react";

export default function Home() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center space-y-4 py-24">
      <div className="w-16 h-16 rounded-2xl bg-zinc-800 border border-zinc-700 flex items-center justify-center">
        <Video className="w-8 h-8 text-zinc-400" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-zinc-300">Selecciona un proyecto</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Elige un proyecto en la barra lateral o crea uno nuevo
        </p>
      </div>
    </div>
  );
}
