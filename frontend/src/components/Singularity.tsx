import { useEffect, useState } from 'react';

interface SingularityProps {
  status: 'idle' | 'running' | 'done' | 'error';
  recentLog?: string;
}

export default function Singularity({ status, recentLog }: SingularityProps) {
  const [displayLog, setDisplayLog] = useState("> [SYS] SYSTEM STANDBY _");
  const isRunning = status === 'running';

  // Optional: blinking effect or intensity based on recentLog but mostly structural now
  return (
    <div className={`magnetic-wrapper flex items-center justify-center transition-all duration-700 ${isRunning ? 'is-running scale-125' : 'scale-90 opacity-60'}`}>
      <div className="magnetic-field-container">
        <div className="magnetic-field">
          <div className="magnetic-line"></div>
          <div className="magnetic-line"></div>
          <div className="magnetic-line"></div>
          <div className="magnetic-line"></div>
          <div className="magnetic-line"></div>
          <div className="magnetic-line"></div>
          
          <div className="magnetic-equator"></div>
          
          <div className="magnetic-core"></div>
        </div>
      </div>
    </div>
  );
}
