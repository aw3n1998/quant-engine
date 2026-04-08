import { useEffect, useRef, useState } from 'react';

interface SingularityProps {
  status: 'idle' | 'running' | 'done' | 'error';
  recentLog?: string;
}

// ─── 粒子系统配置 ────────────────────────────────────────────────────────────
const IDLE_PARTICLES = 30;
const RUNNING_PARTICLES = 120;
const PARTICLE_COLOR_IDLE = '#00FF41';
const PARTICLE_COLOR_RUNNING = '#00FFFF';
const PARTICLE_COLOR_DONE = '#00FF41';
const PARTICLE_COLOR_ERROR = '#C724FF';

interface Particle {
  x: number; y: number;
  vx: number; vy: number;
  life: number; maxLife: number;
  size: number;
}

export default function Singularity({ status, recentLog }: SingularityProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);
  const timeRef = useRef<number>(0);
  const [logText, setLogText] = useState("> [SYS] SYSTEM STANDBY _");

  const isRunning = status === 'running';
  const isDone = status === 'done';
  const isError = status === 'error';

  // 更新 log 文字
  useEffect(() => {
    if (recentLog) {
      setLogText(`> ${recentLog}`);
    } else {
      setLogText(
        status === 'idle' ? '> [SYS] SYSTEM STANDBY _' :
        status === 'running' ? '> [SYS] OPTIMIZING...' :
        status === 'done' ? '> [SYS] CONVERGENCE ACHIEVED' :
        '> [ERR] ANOMALY DETECTED'
      );
    }
  }, [recentLog, status]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2;
    const cy = H / 2;

    // 初始化粒子
    const targetCount = isRunning ? RUNNING_PARTICLES : IDLE_PARTICLES;
    while (particlesRef.current.length < targetCount) {
      particlesRef.current.push(spawnParticle(cx, cy, isRunning));
    }

    function spawnParticle(cx: number, cy: number, fast: boolean): Particle {
      const angle = Math.random() * Math.PI * 2;
      const radius = 20 + Math.random() * 80;
      const speed = fast ? (0.5 + Math.random() * 2) : (0.1 + Math.random() * 0.5);
      const life = 60 + Math.random() * 180;
      return {
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        vx: Math.cos(angle + Math.PI / 2) * speed * (Math.random() > 0.5 ? 1 : -1),
        vy: Math.sin(angle + Math.PI / 2) * speed * (Math.random() > 0.5 ? 1 : -1),
        life,
        maxLife: life,
        size: 1 + Math.random() * (fast ? 3 : 1.5),
      };
    }

    function getOrbitColor() {
      if (isError) return '#C724FF';
      if (isDone) return '#00FF41';
      if (isRunning) return '#00FFFF';
      return '#008F11';
    }

    function getParticleColor() {
      if (isError) return PARTICLE_COLOR_ERROR;
      if (isDone) return PARTICLE_COLOR_DONE;
      if (isRunning) return PARTICLE_COLOR_RUNNING;
      return PARTICLE_COLOR_IDLE;
    }

    function drawOrbits(t: number) {
      const orbitColor = getOrbitColor();
      const speed = isRunning ? 0.012 : 0.003;
      const orbitAlpha = isRunning ? 0.9 : 0.4;

      // 三层椭圆轨道，不同倾斜角
      const orbits = [
        { rx: 100, ry: 38, tilt: 0, dashOffset: t * speed * 400 },
        { rx: 80, ry: 28, tilt: Math.PI / 6, dashOffset: -t * speed * 300 },
        { rx: 60, ry: 20, tilt: -Math.PI / 4, dashOffset: t * speed * 350 },
      ];

      orbits.forEach(({ rx, ry, tilt, dashOffset }) => {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(tilt);
        ctx.beginPath();
        ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
        ctx.strokeStyle = orbitColor;
        ctx.globalAlpha = orbitAlpha;
        ctx.lineWidth = 1;
        ctx.setLineDash([8, 6]);
        ctx.lineDashOffset = dashOffset;
        ctx.stroke();
        ctx.restore();
      });

      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    function drawCore(t: number) {
      // 中心脉冲光晕
      const pulseSize = isRunning
        ? 12 + Math.sin(t * 0.15) * 6
        : 8 + Math.sin(t * 0.04) * 3;

      const coreColor = isError ? '#C724FF' : isRunning ? '#FFFFFF' : isDone ? '#00FF41' : '#008F11';

      // 外发光
      const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseSize * 3);
      grd.addColorStop(0, coreColor + 'CC');
      grd.addColorStop(0.5, coreColor + '44');
      grd.addColorStop(1, 'transparent');
      ctx.beginPath();
      ctx.arc(cx, cy, pulseSize * 3, 0, Math.PI * 2);
      ctx.fillStyle = grd;
      ctx.fill();

      // 中心核心
      ctx.beginPath();
      ctx.arc(cx, cy, pulseSize, 0, Math.PI * 2);
      ctx.fillStyle = coreColor;
      ctx.fill();
    }

    function drawDataStreams(t: number) {
      if (!isRunning) return;
      // 从中心放射的扫描线
      const numStreams = 4;
      for (let i = 0; i < numStreams; i++) {
        const angle = (t * 0.05 + (i * Math.PI * 2) / numStreams) % (Math.PI * 2);
        const len = 90 + Math.sin(t * 0.1 + i) * 20;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(angle) * len, cy + Math.sin(angle) * len);
        ctx.strokeStyle = '#00FFFF';
        ctx.globalAlpha = 0.3;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }

    function drawStatusText() {
      if (isDone) {
        ctx.font = 'bold 10px monospace';
        ctx.fillStyle = '#00FF41';
        ctx.textAlign = 'center';
        ctx.fillText('CONVERGENCE', cx, cy + 120);
      } else if (isError) {
        ctx.font = 'bold 10px monospace';
        ctx.fillStyle = '#C724FF';
        ctx.textAlign = 'center';
        ctx.fillText('ANOMALY DETECTED', cx, cy + 120);
      }
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);

      const t = timeRef.current;

      // 粒子更新与绘制
      const pColor = getParticleColor();
      const targetPCount = isRunning ? RUNNING_PARTICLES : IDLE_PARTICLES;

      // 补充粒子
      while (particlesRef.current.length < targetPCount) {
        particlesRef.current.push(spawnParticle(cx, cy, isRunning));
      }

      particlesRef.current = particlesRef.current
        .map(p => {
          // 向中心施加轻微引力
          const dx = cx - p.x;
          const dy = cy - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const gravStr = isRunning ? 0.02 : 0.005;
          p.vx += (dx / dist) * gravStr;
          p.vy += (dy / dist) * gravStr;

          // 阻尼
          p.vx *= 0.99;
          p.vy *= 0.99;
          p.x += p.vx;
          p.y += p.vy;
          p.life--;

          const alpha = p.life / p.maxLife;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = pColor;
          ctx.globalAlpha = alpha * 0.8;
          ctx.fill();
          ctx.globalAlpha = 1;
          return p;
        })
        .filter(p => p.life > 0 && dist2(p.x, p.y, cx, cy) < 200)
        .slice(0, targetPCount * 1.2);

      drawDataStreams(t);
      drawOrbits(t);
      drawCore(t);
      drawStatusText();

      timeRef.current++;
      animRef.current = requestAnimationFrame(draw);
    }

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [status]);

  return (
    <div className="flex flex-col items-center gap-3">
      <div className={`relative transition-all duration-700 ${isRunning ? 'scale-110' : isDone ? 'scale-100' : 'scale-90 opacity-70'}`}>
        <canvas
          ref={canvasRef}
          width={280}
          height={280}
          className="block"
          style={{ imageRendering: 'pixelated' }}
        />
      </div>

      {/* 日志滚动行 */}
      <div
        className="font-mono text-xs max-w-md text-center px-4 truncate"
        style={{
          color: isError ? '#C724FF' : isRunning ? '#00FFFF' : isDone ? '#00FF41' : '#008F11',
          textShadow: isRunning ? '0 0 8px #00FFFF' : isDone ? '0 0 8px #00FF41' : 'none',
          transition: 'color 0.5s',
        }}
      >
        {logText}
      </div>
    </div>
  );
}

function dist2(x: number, y: number, cx: number, cy: number): number {
  const dx = x - cx;
  const dy = y - cy;
  return Math.sqrt(dx * dx + dy * dy);
}
