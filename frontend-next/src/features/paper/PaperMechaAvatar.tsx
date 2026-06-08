export type PaperMechaUnitId = "purple" | "blue" | "red" | "black" | "grey";
export type PaperMechaVisualState = "idle" | "auto" | "risk" | "loss" | "buy" | "sell" | "profit" | "paused" | "closed";

export const MECHA_UNITS: Record<PaperMechaUnitId, { name: string; desc: string }> = {
  purple: { name: "壹式·紫", desc: "下颚拘束解锁，双眼暴走红光" },
  blue: { name: "零式·蓝白", desc: "中央镜头式单目探测装甲" },
  red: { name: "贰式·赤", desc: "兽化下颚与四复眼突击机体" },
  black: { name: "陆式·黑", desc: "夜战扫描眼罩与青色全息角" },
  grey: { name: "拾参·灰", desc: "神性双重光环与金色核心" },
};

export function PaperMechaAvatar(props: {
  unitId: PaperMechaUnitId;
  state: PaperMechaVisualState;
  mini?: boolean;
}) {
  if (props.unitId === "blue") return <BlueMechaSvg state={props.state} mini={Boolean(props.mini)} />;
  if (props.unitId === "red") return <RedMechaSvg state={props.state} mini={Boolean(props.mini)} />;
  if (props.unitId === "black") return <BlackMechaSvg state={props.state} mini={Boolean(props.mini)} />;
  if (props.unitId === "grey") return <GreyMechaSvg state={props.state} mini={Boolean(props.mini)} />;
  return <PurpleMechaSvg state={props.state} mini={Boolean(props.mini)} />;
}

function PurpleMechaSvg(props: { state: PaperMechaVisualState; mini: boolean }) {
  const active = () => actionActive(props.state);
  const buy = () => props.state === "buy";
  return (
    <svg viewBox="0 0 100 100" class="paper-mecha-action-panel__unit" aria-hidden="true">
      <defs>
        <linearGradient id="paper-next-purple-horn" x1="0%" y1="100%" x2="0%" y2="0%">
          <stop offset="0%" stop-color="rgb(59 7 100)" />
          <stop offset="60%" stop-color="rgb(34 197 94)" />
          <stop offset="100%" stop-color="rgb(74 222 128)" />
        </linearGradient>
        <radialGradient id="paper-next-purple-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgb(253 186 116)" />
          <stop offset="100%" stop-color="rgb(234 88 12)" />
        </radialGradient>
      </defs>
      {!props.mini && buy() ? (
        <g class="paper-mecha-plug-drop">
          <rect x="47" y="5" width="6" height="20" rx="1" fill="rgb(203 213 225)" stroke="rgb(71 85 105)" stroke-width="0.8" />
          <line x1="50" y1="5" x2="50" y2="25" stroke="rgb(148 163 184)" stroke-width="0.5" stroke-dasharray="2 2" />
        </g>
      ) : null}
      {!props.mini ? (
        <>
          <path d="M 12 55 L 2 38 L 5 12 L 18 20 Z" fill="rgb(46 8 82)" stroke="rgb(76 29 149)" stroke-width="1" />
          <polygon points="5,12 11,16 18,20 18,10" fill="rgb(34 197 94)" />
          <path d="M 88 55 L 98 38 L 95 12 L 82 20 Z" fill="rgb(46 8 82)" stroke="rgb(76 29 149)" stroke-width="1" />
          <polygon points="95,12 89,16 82,20 82,10" fill="rgb(34 197 94)" />
        </>
      ) : null}
      <path d="M 36 60 L 50 74 L 64 60 L 58 95 L 42 95 Z" fill="rgb(17 12 44)" stroke="rgb(30 27 75)" stroke-width="1" />
      {!props.mini ? <circle class="animate-core" cx="50" cy="84" r="8" fill="url(#paper-next-purple-core-grad)" /> : null}
      <path d="M 34 52 L 50 20 L 66 52 L 50 62 Z" fill="rgb(59 7 100)" stroke="rgb(107 33 168)" stroke-width="1.5" />
      <path d="M 47 24 L 50 -2 L 53 24 L 50 22 Z" fill="url(#paper-next-purple-horn)" />
      <polygon points="35,44 43,47 38,51" fill="rgb(34 197 94)" />
      <polygon points="65,44 57,47 62,51" fill="rgb(34 197 94)" />
      <g class={buy() ? "paper-mecha-jaw paper-mecha-jaw--open" : "paper-mecha-jaw"}>
        <path d="M 33 53 L 50 67 L 67 53 L 60 46 L 40 46 Z" fill="rgb(30 12 51)" stroke="rgb(76 29 149)" stroke-width="1" />
        {buy() ? <polygon points="41,47 50,56 59,47" fill="rgb(239 68 68)" /> : null}
      </g>
      <polygon points="38,36 49,38 48,43 38,41" fill="rgb(2 6 23)" />
      <polygon points="62,36 51,38 52,43 62,41" fill="rgb(2 6 23)" />
      <polygon class="animate-eye" points="40,37 48,39 45,42" fill={active() ? "rgb(239 68 68)" : "rgb(74 222 128)"} />
      <polygon class="animate-eye" points="60,37 52,39 55,42" fill={active() ? "rgb(239 68 68)" : "rgb(74 222 128)"} />
    </svg>
  );
}

function BlueMechaSvg(props: { state: PaperMechaVisualState; mini: boolean }) {
  const buy = () => props.state === "buy";
  return (
    <svg viewBox="0 0 100 100" class="paper-mecha-action-panel__unit" aria-hidden="true">
      <defs>
        <radialGradient id="paper-next-blue-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgb(252 165 165)" />
          <stop offset="100%" stop-color="rgb(239 68 68)" />
        </radialGradient>
        <radialGradient id="paper-next-blue-lens-reflect" cx="40%" cy="40%" r="60%">
          <stop offset="0%" stop-color="rgb(255 255 255)" />
          <stop offset="40%" stop-color="rgb(239 68 68)" />
          <stop offset="100%" stop-color="rgb(153 27 27)" />
        </radialGradient>
      </defs>
      {!props.mini ? (
        <>
          <path d="M 16 54 C 6 48, 8 20, 22 25 Z" fill="rgb(30 58 138)" stroke="rgb(59 130 246)" stroke-width="1" />
          <path d="M 84 54 C 94 48, 92 20, 78 25 Z" fill="rgb(30 58 138)" stroke="rgb(59 130 246)" stroke-width="1" />
        </>
      ) : null}
      <path d="M 36 60 L 50 74 L 64 60 L 58 95 L 42 95 Z" fill="rgb(71 85 105)" stroke="rgb(203 213 225)" stroke-width="1" />
      {!props.mini ? <circle class="animate-core" cx="50" cy="85" r="7.5" fill="url(#paper-next-blue-core-grad)" /> : null}
      <path d="M 36 54 Q 50 15 64 54 Q 50 63 36 54 Z" fill="rgb(203 213 225)" stroke="rgb(148 163 184)" stroke-width="1.5" />
      <path d="M 48 18 L 52 18 L 52 50 L 48 50 Z" fill="rgb(30 58 138)" />
      <circle cx="41" cy="48" r="1.5" fill="rgb(30 41 59)" />
      <circle cx="59" cy="48" r="1.5" fill="rgb(30 41 59)" />
      <circle cx="45" cy="48" r="1" fill="rgb(30 41 59)" />
      <circle cx="55" cy="48" r="1" fill="rgb(30 41 59)" />
      <circle cx="50" cy="36" r="8.5" fill="rgb(30 41 59)" stroke="rgb(249 115 22)" stroke-width="1" />
      <circle class={buy() ? "animate-eye paper-mecha-lens paper-mecha-lens--scan" : "animate-eye paper-mecha-lens"} cx="50" cy="36" r="6.5" fill="url(#paper-next-blue-lens-reflect)" />
      <circle cx="52" cy="34" r="2" fill="rgb(255 255 255)" />
    </svg>
  );
}

function RedMechaSvg(props: { state: PaperMechaVisualState; mini: boolean }) {
  const buy = () => props.state === "buy";
  return (
    <svg viewBox="0 0 100 100" class="paper-mecha-action-panel__unit" aria-hidden="true">
      <defs>
        <radialGradient id="paper-next-red-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgb(167 243 208)" />
          <stop offset="100%" stop-color="rgb(16 185 129)" />
        </radialGradient>
      </defs>
      {!props.mini ? (
        <>
          <polygon points="12,50 3,38 8,15 22,22" fill="rgb(153 27 27)" stroke="rgb(220 38 38)" stroke-width="1" />
          <polygon points="8,15 15,18 22,22 20,8" fill="rgb(251 191 36)" />
          <polygon points="88,50 97,38 92,15 78,22" fill="rgb(153 27 27)" stroke="rgb(220 38 38)" stroke-width="1" />
          <polygon points="92,15 85,18 78,22 80,8" fill="rgb(251 191 36)" />
        </>
      ) : null}
      <path d="M 35 60 L 50 72 L 65 60 L 59 95 L 41 95 Z" fill="rgb(63 7 18)" stroke="rgb(153 27 27)" stroke-width="1" />
      {!props.mini ? <circle class="animate-core" cx="50" cy="82" r="8" fill="url(#paper-next-red-core-grad)" /> : null}
      <path d="M 33 50 L 50 20 L 67 50 L 50 62 Z" fill="rgb(153 27 27)" stroke="rgb(220 38 38)" stroke-width="1.5" />
      <path d="M 40 25 L 24 10 L 42 18 Z" fill="rgb(153 27 27)" stroke="rgb(220 38 38)" stroke-width="1" />
      <path d="M 60 25 L 76 10 L 58 18 Z" fill="rgb(153 27 27)" stroke="rgb(220 38 38)" stroke-width="1" />
      <polygon points="41,21 50,26 59,21 50,18" fill="rgb(248 250 252)" stroke="rgb(148 163 184)" stroke-width="0.8" />
      <g class={buy() ? "paper-mecha-jaw paper-mecha-jaw--beast" : "paper-mecha-jaw"}>
        <polygon points="40,51 50,58 60,51 50,46" fill="rgb(31 3 10)" stroke="rgb(220 38 38)" stroke-width="0.8" />
        {buy() ? <path d="M 43 49 L 45 52 L 47 49 L 49 52 L 51 49 L 53 52 L 55 49 L 57 52" fill="none" stroke="rgb(255 255 255)" stroke-width="1" /> : null}
      </g>
      <circle class="animate-eye" cx="43" cy="35" r={buy() ? 3.2 : 2.5} fill="rgb(16 185 129)" />
      <circle class="animate-eye" cx="57" cy="35" r={buy() ? 3.2 : 2.5} fill="rgb(16 185 129)" />
      <circle class="animate-eye" cx="41" cy="44" r={buy() ? 3.2 : 2.5} fill="rgb(16 185 129)" />
      <circle class="animate-eye" cx="59" cy="44" r={buy() ? 3.2 : 2.5} fill="rgb(16 185 129)" />
    </svg>
  );
}

function BlackMechaSvg(props: { state: PaperMechaVisualState; mini: boolean }) {
  const active = () => actionActive(props.state);
  return (
    <svg viewBox="0 0 100 100" class="paper-mecha-action-panel__unit" aria-hidden="true">
      <defs>
        <radialGradient id="paper-next-black-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgb(207 250 254)" />
          <stop offset="100%" stop-color="rgb(6 182 212)" />
        </radialGradient>
      </defs>
      {!props.mini ? (
        <>
          <path d="M 14 48 L 1 32 L 8 16 L 22 24 Z" fill="rgb(15 23 42)" stroke="rgb(51 65 85)" stroke-width="1" />
          <line x1="8" y1="16" x2="22" y2="24" stroke="rgb(6 182 212)" stroke-width="1.5" />
          <path d="M 86 48 L 99 32 L 92 16 L 78 24 Z" fill="rgb(15 23 42)" stroke="rgb(51 65 85)" stroke-width="1" />
          <line x1="92" y1="16" x2="78" y2="24" stroke="rgb(6 182 212)" stroke-width="1.5" />
        </>
      ) : null}
      <path d="M 35 60 L 50 72 L 65 60 L 58 95 L 42 95 Z" fill="rgb(2 6 23)" stroke="rgb(30 41 59)" stroke-width="1" />
      {!props.mini ? <circle class="animate-core" cx="50" cy="83" r="7.5" fill="url(#paper-next-black-core-grad)" /> : null}
      <path d="M 33 54 L 50 18 L 67 54 L 50 63 Z" fill="rgb(15 23 42)" stroke="rgb(30 41 59)" stroke-width="1.5" />
      <path d="M 49 18 L 51 3 L 53 18 Z" fill="rgb(6 182 212)" />
      <path class="animate-eye" d="M 37 38 Q 50 44 63 38 Q 50 48 37 38" fill="none" stroke={active() ? "rgb(244 63 94)" : "rgb(34 211 238)"} stroke-width={active() ? 4 : 3} />
    </svg>
  );
}

function GreyMechaSvg(props: { state: PaperMechaVisualState; mini: boolean }) {
  const buy = () => props.state === "buy" || props.state === "profit";
  return (
    <svg viewBox="0 0 100 100" class="paper-mecha-action-panel__unit" aria-hidden="true">
      <defs>
        <radialGradient id="paper-next-grey-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgb(255 251 235)" />
          <stop offset="100%" stop-color="rgb(245 158 11)" />
        </radialGradient>
      </defs>
      {!props.mini && buy() ? (
        <g class="paper-mecha-halo">
          <ellipse cx="50" cy="15" rx="20" ry="4" fill="none" stroke="rgb(251 191 36)" stroke-width="1" />
          <ellipse cx="50" cy="10" rx="15" ry="3" fill="none" stroke="rgb(245 158 11)" stroke-width="0.8" />
        </g>
      ) : null}
      {!props.mini ? (
        <>
          <path d="M 16 52 L 5 40 L 7 15 L 21 21 Z" fill="rgb(71 85 105)" stroke="rgb(100 116 139)" stroke-width="1" />
          <path d="M 84 52 L 95 40 L 93 15 L 79 21 Z" fill="rgb(71 85 105)" stroke="rgb(100 116 139)" stroke-width="1" />
        </>
      ) : null}
      <path d="M 36 58 L 50 72 L 64 58 L 58 95 L 42 95 Z" fill="rgb(51 65 85)" stroke="rgb(100 116 139)" stroke-width="1" />
      {!props.mini ? <circle class="animate-core" cx="50" cy="81" r="8" fill="url(#paper-next-grey-core-grad)" /> : null}
      <path d="M 32 54 L 50 22 L 68 54 L 50 66 Z" fill="rgb(71 85 105)" stroke="rgb(100 116 139)" stroke-width="1.5" />
      <path d="M 43 24 L 41 2 L 49 22 Z" fill="rgb(245 158 11)" />
      <path d="M 57 24 L 59 2 L 51 22 Z" fill="rgb(245 158 11)" />
      <circle class="animate-eye" cx="42" cy="36" r="2.2" fill={buy() ? "rgb(239 68 68)" : "rgb(251 191 36)"} />
      <circle class="animate-eye" cx="58" cy="36" r="2.2" fill={buy() ? "rgb(239 68 68)" : "rgb(251 191 36)"} />
      <circle class="animate-eye" cx="45" cy="43" r="2" fill={buy() ? "rgb(239 68 68)" : "rgb(251 191 36)"} />
      <circle class="animate-eye" cx="55" cy="43" r="2" fill={buy() ? "rgb(239 68 68)" : "rgb(251 191 36)"} />
    </svg>
  );
}

function actionActive(state: PaperMechaVisualState): boolean {
  return state === "buy" || state === "risk" || state === "loss";
}
