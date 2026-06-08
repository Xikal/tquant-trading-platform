import type { JSX } from "solid-js";

export function Icon(props: {
  name: string;
  class?: string;
  spin?: boolean;
  spinClass?: string;
  title?: string;
  "aria-label"?: string;
}) {
  const className = () => [props.class, props.spin ? props.spinClass : ""].filter(Boolean).join(" ") || undefined;
  const hidden = () => (props.title || props["aria-label"] ? undefined : true);
  return (
    <svg viewBox="0 0 24 24" aria-hidden={hidden()} aria-label={props["aria-label"] ?? props.title} class={className()}>
      <IconPath name={props.name} />
    </svg>
  );
}

function IconPath(props: { name: string }): JSX.Element {
  switch (props.name) {
    case "activity":
    case "pulse":
      return <path d="M3 12h4l2-6 4 12 2-6h6" />;
    case "alert":
      return <><path d="M12 3 3 20h18L12 3Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></>;
    case "award":
      return <><circle cx="12" cy="9" r="5" /><path d="m9 14-2 7 5-3 5 3-2-7" /></>;
    case "bar":
      return <path d="M5 19V9m7 10V5m7 14v-7" />;
    case "bell":
      return <><path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z" /><path d="M10 21h4" /></>;
    case "branch":
      return <><path d="M6 4v6a4 4 0 0 0 4 4h8" /><circle cx="6" cy="4" r="2" /><circle cx="18" cy="14" r="2" /><path d="M12 6h4a2 2 0 0 1 2 2v4" /></>;
    case "briefcase":
      return <><path d="M10 6V5a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1" /><path d="M4 7h16v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7Z" /><path d="M4 12h16" /></>;
    case "check":
      return <path d="m5 12 4 4L19 6" />;
    case "chevron":
      return <path d="M9 5 16 12 9 19" />;
    case "chevron-down":
    case "chevronDown":
      return <path d="m6 9 6 6 6-6" />;
    case "clipboard":
      return <><path d="M9 4h6l1 2h3v14H5V6h3l1-2Z" /><path d="M9 10h6M9 14h6M9 18h4" /></>;
    case "clock":
      return <><circle cx="12" cy="12" r="8" /><path d="M12 8v5l3 2" /></>;
    case "compass":
      return <><circle cx="12" cy="12" r="9" /><path d="m15 9-2 5-5 2 2-5 5-2Z" /></>;
    case "cpu":
      return <><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M4 10h3M4 14h3M17 10h3M17 14h3M10 4v3M14 4v3M10 17v3M14 17v3" /></>;
    case "database":
      return <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></>;
    case "eye":
      return <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>;
    case "eyeOff":
      return <><path d="M3 3l18 18" /><path d="M10.6 10.6A3 3 0 0 0 12 15a3 3 0 0 0 2.4-1.2" /><path d="M9.5 5.7A10.5 10.5 0 0 1 12 5c6.5 0 10 7 10 7a16 16 0 0 1-3.1 4.1M6.6 6.6A16 16 0 0 0 2 12s3.5 7 10 7c1.3 0 2.5-.3 3.6-.8" /></>;
    case "file":
      return <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z" /><path d="M14 3v6h6" /><path d="M8 13h8M8 17h5" /></>;
    case "filter":
      return <path d="M4 5h16l-6 7v5l-4 2v-7L4 5Z" />;
    case "flame":
      return <path d="M12 22c4 0 7-2.7 7-6.5 0-2.7-1.5-4.8-3.3-6.7-.6 2.4-1.8 3.2-3 4.2.4-3-1.1-5.7-4.1-8.9.2 4-2.6 6.2-3.4 9.3C4.1 18 7.5 22 12 22Z" />;
    case "grid":
      return <><path d="M4 4h7v7H4V4ZM13 4h7v7h-7V4ZM4 13h7v7H4v-7ZM13 13h7v7h-7v-7Z" /></>;
    case "info":
      return <><circle cx="12" cy="12" r="9" /><path d="M12 10v6" /><path d="M12 7h.01" /></>;
    case "key":
      return <><circle cx="8" cy="14" r="4" /><path d="m11 11 7-7" /><path d="m16 4 4 4" /><path d="m14 6 4 4" /></>;
    case "layers":
      return <><path d="M12 2 22 7 12 12 2 7l10-5Z" /><path d="m2 12 10 5 10-5" /><path d="m2 17 10 5 10-5" /></>;
    case "line":
      return <><path d="M4 17h16" /><path d="M5 14l4-4 3 3 6-7" /></>;
    case "list":
      return <><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></>;
    case "lock":
      return <><path d="M7 10V7a5 5 0 0 1 10 0v3" /><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M12 14v3" /></>;
    case "moon":
      return <path d="M20 15.5A8.5 8.5 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z" />;
    case "package":
      return <><path d="M12 3 4 7v10l8 4 8-4V7l-8-4Z" /><path d="m4 7 8 4 8-4M12 11v10" /></>;
    case "phone":
      return <><rect x="6" y="2" width="12" height="20" rx="2" /><path d="M11 18h2" /></>;
    case "play":
      return <path d="M8 5v14l11-7-11-7Z" />;
    case "plus":
      return <path d="M12 5v14M5 12h14" />;
    case "qr":
      return <><path d="M3 3h7v7H3V3ZM14 3h7v7h-7V3ZM3 14h7v7H3v-7Z" /><path d="M14 14h2v2h-2v-2ZM19 14h2v5h-5v-2h3v-3ZM14 19h2v2h-2v-2Z" /></>;
    case "refresh":
      return <><path d="M20 6v5h-5" /><path d="M4 18v-5h5" /><path d="M18.6 9a7 7 0 0 0-11.4-2.4L4 10" /><path d="M5.4 15a7 7 0 0 0 11.4 2.4L20 14" /></>;
    case "save":
      return <><path d="M4 3h13l3 3v15H4V3Z" /><path d="M8 3v6h7V3M8 17h8" /></>;
    case "search":
      return <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>;
    case "server":
      return <><rect x="4" y="5" width="16" height="6" rx="2" /><rect x="4" y="13" width="16" height="6" rx="2" /><path d="M8 8h.01M8 16h.01" /></>;
    case "shield":
      return <><path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-5" /></>;
    case "sliders":
      return <><path d="M4 6h7M15 6h5M4 16h3M11 16h9" /><path d="M11 4v4M7 14v4" /></>;
    case "sun":
      return <><circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M19.8 4.2l-2.1 2.1M6.3 17.7l-2.1 2.1" /></>;
    case "terminal":
      return <><path d="m5 7 5 5-5 5" /><path d="M12 17h7" /></>;
    case "trend":
    case "trendUp":
      return <path d="M4 19h16M6 16l4-5 4 3 5-8" />;
    case "trendDown":
      return <path d="M4 5h16M6 8l4 5 4-3 5 8" />;
    case "unlock":
      return <><path d="M7 10V7a5 5 0 0 1 9.7-1.7" /><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M12 14v3" /></>;
    case "wallet":
      return <><path d="M4 7h16v12H4V7Z" /><path d="M4 10h16M16 14h2" /></>;
    case "x":
      return <path d="M6 6l12 12M18 6 6 18" />;
    default:
      return <path d="M12 5v14M5 12h14" />;
  }
}
