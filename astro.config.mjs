// @ts-check
import { defineConfig } from "astro/config";
import { unified } from "@astrojs/markdown-remark";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

export default defineConfig({
  site: "https://owenmedeiros.com",
  // Astro's HTML compressor drops whitespace-only runs that span a newline, so
  // a link starting on its own line loses the space before it ("and some<a>").
  // The pages are small and JS-free; keeping the authored whitespace is cheaper
  // than reflowing prose around the compressor.
  compressHTML: false,
  redirects: {
    "/contact": "/about",
    "/publications": "/research",
    "/thesis": "/research",
    "/talks": "/research",
  },
  markdown: {
    processor: unified({
      remarkPlugins: [remarkMath],
      rehypePlugins: [rehypeKatex],
    }),
  },
});
