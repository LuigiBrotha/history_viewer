// Google's Turbo colormap, using its published polynomial approximation (Mikhailov, 2019).
const RED = [0.13572138, 4.6153926, -42.66032258, 132.13108234, -152.94239396, 59.28637943];
const GREEN = [0.09140261, 2.19418839, 4.84296658, -14.18503333, 4.27729857, 2.82956604];
const BLUE = [0.1066733, 12.64194608, -60.58204836, 110.36276771, -89.90310912, 27.34824973];
const GRADIENT_STOPS = 16;

function clamp(value) {
  return Math.min(1, Math.max(0, value));
}

function channel(coefficients, x) {
  const value = coefficients.reduce((sum, coefficient, power) => sum + coefficient * x ** power, 0);
  return Math.round(clamp(value) * 255).toString(16).padStart(2, "0");
}

export function turboColor(value) {
  const x = clamp(value);
  return `#${channel(RED, x)}${channel(GREEN, x)}${channel(BLUE, x)}`;
}

export function rampGradient() {
  const stops = [];
  for (let i = 0; i <= GRADIENT_STOPS; i++) {
    stops.push(turboColor(i / GRADIENT_STOPS));
  }
  return `linear-gradient(to right, ${stops.join(", ")})`;
}
