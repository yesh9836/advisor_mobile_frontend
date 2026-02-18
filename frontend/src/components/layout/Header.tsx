import { useAuth } from "@/context/AuthContext";
import brandLogo from "@/assets/Spectaculeads-logo.jpeg";

interface HeaderProps {
  onMenuClick?: () => void;
}

const Header = ({ onMenuClick }: HeaderProps) => {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <button type="button" className="header-menu" onClick={onMenuClick} aria-label="Open navigation">
          Menu
        </button>

        <div className="brand">
          <img className="brand-logo" src={brandLogo} alt="Spectaculeads logo" />
        </div>

        <div className="header-user-controls">
          <div className="user-meta">
            <p className="user-meta-name">{user?.name ?? "Advisor"}</p>
            <p className="user-meta-email">{user?.email ?? ""}</p>
          </div>

          <button type="button" className="logout-btn" onClick={logout}>
            Logout
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
