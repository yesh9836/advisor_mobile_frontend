import type { SubmitEvent } from "react";

import { useAuth } from "@/context/AuthContext";

interface HeaderProps {
  onMenuClick?: () => void;
}

const SearchIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true" className="search-icon">
    <circle cx="9" cy="9" r="6" fill="none" stroke="currentColor" strokeWidth="1.8" />
    <path d="M13.5 13.5L18 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

const BellIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path
      d="M10 3.5a4.5 4.5 0 0 0-4.5 4.5V11l-1.4 2.3a1 1 0 0 0 .86 1.5h10.08a1 1 0 0 0 .86-1.5L14.5 11V8A4.5 4.5 0 0 0 10 3.5Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    />
    <path d="M8.2 15.3a1.8 1.8 0 0 0 3.6 0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const GearIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path
      d="M11.8 2.8 12.3 4a6.5 6.5 0 0 1 1.2.5l1.2-.5 1.4 1.4-.5 1.2c.2.4.4.8.5 1.2l1.2.5v2l-1.2.5a6.5 6.5 0 0 1-.5 1.2l.5 1.2-1.4 1.4-1.2-.5a6.5 6.5 0 0 1-1.2.5l-.5 1.2h-2l-.5-1.2a6.5 6.5 0 0 1-1.2-.5l-1.2.5-1.4-1.4.5-1.2a6.5 6.5 0 0 1-.5-1.2L2.8 11v-2l1.2-.5c.1-.4.3-.8.5-1.2l-.5-1.2L5.4 4l1.2.5c.4-.2.8-.4 1.2-.5l.5-1.2h2Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinejoin="round"
    />
    <circle cx="10" cy="10" r="2.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
  </svg>
);

const Header = ({ onMenuClick }: HeaderProps) => {
  const { user, logout } = useAuth();

  const onSearchSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
  };

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <button type="button" className="header-menu" onClick={onMenuClick} aria-label="Open navigation">
          Menu
        </button>

        <div className="brand">
          <div className="brand-badge">✦</div>
          <div>
            <p className="brand-title">Spectaculeads</p>
            <p className="brand-subtitle">Lead Marketplace</p>
          </div>
        </div>

        <form className="header-search" onSubmit={onSearchSubmit}>
          <SearchIcon />
          <input type="search" placeholder="Search..." aria-label="Search" />
        </form>

        <div className="header-actions">
          <button type="button" className="icon-btn" aria-label="Notifications">
            <BellIcon />
          </button>
          <button type="button" className="icon-btn" aria-label="Settings">
            <GearIcon />
          </button>
          <span className="view-pill">Advisor View</span>
        </div>

        <div className="user-meta">
          <p className="user-meta-name">{user?.name ?? "Advisor"}</p>
          <p className="user-meta-email">{user?.email ?? ""}</p>
        </div>

        <button type="button" className="logout-btn" onClick={logout}>
          Logout
        </button>
      </div>
    </header>
  );
};

export default Header;
