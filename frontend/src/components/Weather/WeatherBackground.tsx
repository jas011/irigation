import React, { useEffect, useRef } from "react";

interface WeatherBackgroundProps {
  iconType: string;
  isDay: boolean;
}

const WeatherBackground: React.FC<WeatherBackgroundProps> = ({ iconType, isDay }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const isRainy = ["rain", "heavy_rain", "drizzle", "thunderstorm"].includes(iconType);
  const isSnow = iconType === "snow";
  const isNight = !isDay && ["sunny", "mostly_sunny", "clear_night", "partly_cloudy_night"].includes(iconType);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Check prefers-reduced-motion
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    // Particle setup
    const particles: Array<{
      x: number;
      y: number;
      speed: number;
      length?: number;
      radius?: number;
      opacity: number;
      drift?: number;
    }> = [];

    const count = isRainy ? (iconType === "heavy_rain" || iconType === "thunderstorm" ? 140 : 80) : isSnow ? 70 : isNight ? 90 : 0;

    for (let i = 0; i < count; i++) {
      if (isRainy) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          speed: 8 + Math.random() * 12,
          length: 12 + Math.random() * 18,
          opacity: 0.15 + Math.random() * 0.35,
          drift: 1.5 + Math.random() * 2,
        });
      } else if (isSnow) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          speed: 1 + Math.random() * 2.5,
          radius: 1.5 + Math.random() * 2.5,
          opacity: 0.2 + Math.random() * 0.6,
          drift: (Math.random() - 0.5) * 1.5,
        });
      } else if (isNight) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height * 0.7,
          speed: 0.05 + Math.random() * 0.1,
          radius: 0.8 + Math.random() * 1.6,
          opacity: 0.2 + Math.random() * 0.7,
        });
      }
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      if (isRainy) {
        ctx.strokeStyle = "rgba(59, 130, 246, 0.4)";
        ctx.lineWidth = iconType === "heavy_rain" ? 1.8 : 1.2;
        ctx.lineCap = "round";

        particles.forEach((p) => {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p.x + (p.drift || 1), p.y + (p.length || 15));
          ctx.stroke();

          p.y += p.speed;
          p.x += p.drift || 1;

          if (p.y > height) {
            p.y = -20;
            p.x = Math.random() * width;
          }
          if (p.x > width) {
            p.x = 0;
          }
        });
      } else if (isSnow) {
        ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
        particles.forEach((p) => {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.radius || 2, 0, Math.PI * 2);
          ctx.fill();

          p.y += p.speed;
          p.x += p.drift || 0;

          if (p.y > height) {
            p.y = -10;
            p.x = Math.random() * width;
          }
        });
      } else if (isNight) {
        particles.forEach((p) => {
          ctx.fillStyle = `rgba(255, 255, 255, ${p.opacity})`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.radius || 1, 0, Math.PI * 2);
          ctx.fill();

          p.opacity += (Math.random() - 0.5) * 0.04;
          if (p.opacity < 0.1) p.opacity = 0.1;
          if (p.opacity > 0.8) p.opacity = 0.8;
        });
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [iconType, isDay, isNight, isRainy, isSnow]);

  // Determine container classes
  let bgClass = "weather-bg-sunny";
  if (!isDay) {
    bgClass = "weather-bg-night";
  } else if (iconType === "thunderstorm") {
    bgClass = "weather-bg-thunderstorm";
  } else if (iconType === "heavy_rain" || iconType === "rain" || iconType === "drizzle") {
    bgClass = "weather-bg-rain";
  } else if (iconType === "cloudy" || iconType === "partly_cloudy") {
    bgClass = "weather-bg-cloudy";
  } else if (iconType === "fog") {
    bgClass = "weather-bg-fog";
  } else if (iconType === "snow") {
    bgClass = "weather-bg-snow";
  }

  return (
    <div className={`weather-bg-container ${bgClass}`}>
      {/* Sun glow elements for clear daytime */}
      {isDay && (iconType === "sunny" || iconType === "mostly_sunny") && (
        <>
          <div className="sun-glow-orb" />
          <div className="sun-beam" />
        </>
      )}

      {/* Moving cloud layer for cloudy / overcast */}
      {(iconType === "cloudy" || iconType === "partly_cloudy" || iconType === "thunderstorm") && (
        <div className="weather-cloud-layer" />
      )}

      {/* Lightning flash for thunderstorm */}
      {iconType === "thunderstorm" && <div className="weather-lightning-flash" />}

      {/* Fog mist layer */}
      {iconType === "fog" && <div className="weather-fog-layer" />}

      {/* Moon glow for night */}
      {!isDay && <div className="weather-moon-glow" />}

      {/* Canvas for dynamic particles (rain, snow, night stars) */}
      {(isRainy || isSnow || isNight) && <canvas ref={canvasRef} className="weather-rain-canvas" />}
    </div>
  );
};

export default WeatherBackground;
