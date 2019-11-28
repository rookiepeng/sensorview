import React from "react";
import Worldview, { Spheres, Axes } from "regl-worldview";

export default function Example() {
  const radius = 20;
  const steps = 100;
  const deltaRadian = (2 * Math.PI) / steps;

  function numberToColor(number, max, a = 1) {
    const i = (number * 255) / max;
    const r = Math.round(Math.sin(0.024 * i + 0) * 127 + 128) / 255;
    const g = Math.round(Math.sin(0.024 * i + 2) * 127 + 128) / 255;
    const b = Math.round(Math.sin(0.024 * i + 4) * 127 + 128) / 255;
    return { r, g, b, a };
  }
  const marker = {
    pose: {
      orientation: { x: 0, y: 0, z: 0, w: 1 },
      position: { x: 0, y: 0, z: 0 }
    },
    scale: { x: 1, y: 1, z: 1 },
    colors: [],
    points: []
  };

  new Array(steps)
    .fill()
    .map((_, idx) => [
      radius * Math.cos(deltaRadian * idx),
      radius * Math.sin(deltaRadian * idx)
    ])
    .forEach(([coord1, coord2], idx) => {
      const color = numberToColor(idx, steps);
      marker.colors.push(...[color, color, color]);
      marker.points.push({ x: coord1, y: coord2, z: 0 });
      marker.points.push({ x: 0, y: coord1, z: coord2 });
      marker.points.push({ x: coord2, y: 0, z: coord1 });
    });

  return (
    <Worldview>
      <Spheres>{[marker]}</Spheres>
      <Axes />
    </Worldview>
  );
}
