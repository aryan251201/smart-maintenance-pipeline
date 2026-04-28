import { useState, useEffect } from "react";
import DeviceCard from "./components/DeviceCard";
import SensorChart from "./components/SensorChart";
import AlertHistory from "./components/AlertHistory";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const POLL_INTERVAL = 5000;

function App() {
  const [predictions, setPredictions] = useState([]);
  const [sensorData, setSensorData] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState("device-001");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [selectedDevice]);

  async function fetchData() {
    try {
      const [predRes, sensorRes] = await Promise.all([
        fetch(`${API_URL}/predict`),
        fetch(`${API_URL}/sensors/recent?device_id=${selectedDevice}&limit=100`),
      ]);
      if (predRes.ok) setPredictions(await predRes.json());
      if (sensorRes.ok) setSensorData(await sensorRes.json());
    } catch (err) {
      console.error("Fetch error:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <header className="max-w-7xl mx-auto mb-8">
        <h1 className="text-3xl font-bold">IoT Predictive Maintenance</h1>
        <p className="text-gray-400 mt-1">Real-time failure prediction dashboard</p>
      </header>

      <main className="max-w-7xl mx-auto space-y-8">
        {/* Device Status Cards */}
        <section>
          <h2 className="text-xl font-semibold mb-4">Device Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {predictions.map((pred) => (
              <DeviceCard
                key={pred.device_id}
                prediction={pred}
                selected={pred.device_id === selectedDevice}
                onClick={() => setSelectedDevice(pred.device_id)}
              />
            ))}
          </div>
        </section>

        {/* Sensor Charts */}
        <section>
          <h2 className="text-xl font-semibold mb-4">
            Sensor Readings — {selectedDevice}
          </h2>
          {loading ? (
            <p className="text-gray-400">Loading...</p>
          ) : (
            <SensorChart data={sensorData} />
          )}
        </section>

        {/* Alert History */}
        <section>
          <h2 className="text-xl font-semibold mb-4">Recent Alerts</h2>
          <AlertHistory apiUrl={API_URL} />
        </section>
      </main>
    </div>
  );
}

export default App;
