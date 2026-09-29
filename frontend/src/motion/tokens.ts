/**
 * frontend/src/motion/tokens.ts
 * Design system motion tokens & Framer Motion variants.
 * Respects prefers-reduced-motion for accessibility.
 */

export const transitions = {
  snappy: { type: "spring", stiffness: 400, damping: 30 },
  gentle: { type: "spring", stiffness: 200, damping: 25 },
  smooth: { duration: 0.25, ease: [0.16, 1, 0.3, 1] },
};

export const panelVariants = {
  open: {
    x: 0,
    opacity: 1,
    transition: transitions.gentle,
  },
  closed: {
    x: -360,
    opacity: 0,
    transition: transitions.snappy,
  },
};

export const fadeIn = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: transitions.smooth,
  },
  exit: {
    opacity: 0,
    y: -8,
    transition: { duration: 0.15 },
  },
};

export const cardStagger = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
    },
  },
};
