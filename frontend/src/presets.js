/** Generic fallbacks. Real action list is loaded after unlock from GET /api/presets. */

export const ACTION_PRESETS = [
  {
    id: "enhance",
    label: "Enhance",
    hint: "keep outfit · subtle",
    mode: "img",
    prompt: "Photorealistic edit of the person in the start image. Keep identity, pose, lighting, background, and the same clothes. Apply a subtle clothed enhance.",
  },
  {
    id: "style",
    label: "Style",
    hint: "same scene",
    mode: "img",
    prompt: "Photorealistic edit of the person in the start image. Keep identity and framing. Apply a mild style refine.",
  },
  {
    id: "animate",
    label: "Animate",
    hint: "image to video",
    mode: "vid",
    prompt: "Gentle natural motion. Keep identity, clothing, and framing. One continuous shot.",
  },
];

export function setActionPresets(list) {
  if (!Array.isArray(list) || !list.length) return;
  ACTION_PRESETS.splice(0, ACTION_PRESETS.length, ...list);
}

export function presetsForMode(mode) {
  return ACTION_PRESETS.filter((p) => p.mode === mode);
}

export function presetById(id) {
  return ACTION_PRESETS.find((p) => p.id === id) || null;
}
