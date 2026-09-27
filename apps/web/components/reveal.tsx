"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";

type RevealProps = {
  as?: "article" | "div" | "li" | "section";
  children: ReactNode;
  className?: string;
  delay?: number;
  id?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
};

export function Reveal({
  as = "div",
  children,
  className,
  delay = 0,
  id,
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
}: RevealProps) {
  const reduceMotion = useReducedMotion();
  const props = {
    className,
    id,
    "aria-label": ariaLabel,
    "aria-labelledby": ariaLabelledBy,
    initial: reduceMotion ? false : { opacity: 0.88, y: 18 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, amount: 0.16 as const },
    transition: {
      duration: reduceMotion ? 0 : 0.48,
      delay: reduceMotion ? 0 : delay,
      ease: "easeOut" as const,
    },
  };

  if (as === "article") {
    return <motion.article {...props}>{children}</motion.article>;
  }
  if (as === "li") {
    return <motion.li {...props}>{children}</motion.li>;
  }
  if (as === "section") {
    return <motion.section {...props}>{children}</motion.section>;
  }
  return <motion.div {...props}>{children}</motion.div>;
}
