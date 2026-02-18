import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { getMyDeliverySettings } from "@/api/delivery-settings";
import { useAuth } from "@/context/AuthContext";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SidebarItem {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
}

interface DeliverySettingsChangeDetail {
  email_alerts_enabled: boolean;
  sms_alerts_enabled: boolean;
}

const DELIVERY_SETTINGS_CHANGED_EVENT = "delivery-settings-changed";

const DashboardIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path d="M3 10h6V3H3v7Zm8 7h6V3h-6v14ZM3 17h6v-5H3v5Z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
  </svg>
);

const BuyIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <rect x="3" y="5" width="14" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M3 8h14" fill="none" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

const InboxIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path d="M3 4h14l-4.5 5h-5L3 4Z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    <path d="M3 4v11h14V4M7 15c.8-1.2 1.7-1.8 3-1.8s2.2.6 3 1.8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const BillingIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path d="M5 3.5h10v13l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5v-13Z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    <path d="M7.5 7.5h5M7.5 10.2h5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const ProfileIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <circle cx="10" cy="6.5" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M4.5 16c.8-2.4 2.7-3.7 5.5-3.7s4.7 1.3 5.5 3.7" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const InventoryIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path d="M10 2.8 16.5 6v8L10 17.2 3.5 14V6L10 2.8Z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    <path d="M3.5 6 10 9.2 16.5 6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
  </svg>
);

const OrdersIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <rect x="3" y="4.5" width="14" height="11" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M6.5 8h7M6.5 11h4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const UsersIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <circle cx="7" cy="7" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <circle cx="13.5" cy="8.5" r="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M3.5 15c.7-2 2.2-3 4.5-3s3.8 1 4.5 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M11.5 14.8c.5-1.4 1.5-2.2 3-2.2 1 0 1.8.3 2.5 1" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const ImportIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path d="M10 3v9M6.5 8.5 10 12l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M4 15.5h12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const LicenseIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <rect x="3.5" y="3.5" width="13" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M6.5 8.5h7M6.5 11.5h4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const AnalyticsIcon = () => (
  <svg viewBox="0 0 20 20" aria-hidden="true">
    <path d="M3.5 15.5h13" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M6 13V9.5M10 13V6.5M14 13V8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const Sidebar = ({ isOpen, onClose }: SidebarProps) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  const [showConfigureNotificationsCta, setShowConfigureNotificationsCta] =
    useState(false);

  const advisorItems: SidebarItem[] = [
    { to: "/dashboard", label: "Dashboard", icon: <DashboardIcon />, end: true },
    { to: "/subscription", label: "Buy Leads", icon: <BuyIcon /> },
    { to: "/leads", label: "Lead Inbox", icon: <InboxIcon /> },
    { to: "/profile", label: "Profile", icon: <ProfileIcon /> },
    { to: "/billing", label: "Billing", icon: <BillingIcon /> },
  ];

  const adminItems: SidebarItem[] = [
    { to: "/admin", label: "Dashboard", icon: <DashboardIcon />, end: true },
    { to: "/admin/lead-inventory", label: "Lead Inventory", icon: <InventoryIcon /> },
    { to: "/admin/users", label: "Users", icon: <UsersIcon /> },
    { to: "/admin/orders", label: "Orders", icon: <OrdersIcon /> },
    { to: "/admin/imports", label: "Imports", icon: <ImportIcon /> },
    { to: "/admin/analytics", label: "Analytics", icon: <AnalyticsIcon /> },
    { to: "/admin/license-reviews", label: "License Reviews", icon: <LicenseIcon /> },
  ];

  const items = isAdmin ? adminItems : advisorItems;

  useEffect(() => {
    if (isAdmin) {
      setShowConfigureNotificationsCta(false);
      return;
    }

    let isMounted = true;

    const handleDeliverySettingsChanged = (event: Event) => {
      const customEvent = event as CustomEvent<DeliverySettingsChangeDetail>;
      const detail = customEvent.detail;
      if (!detail) {
        return;
      }
      const shouldShowCta =
        !detail.email_alerts_enabled && !detail.sms_alerts_enabled;
      setShowConfigureNotificationsCta(shouldShowCta);
    };

    window.addEventListener(
      DELIVERY_SETTINGS_CHANGED_EVENT,
      handleDeliverySettingsChanged,
    );

    const loadDeliverySettings = async () => {
      try {
        const settings = await getMyDeliverySettings();
        if (!isMounted) {
          return;
        }
        const shouldShowCta =
          !settings.email_alerts_enabled && !settings.sms_alerts_enabled;
        setShowConfigureNotificationsCta(shouldShowCta);
      } catch {
        if (isMounted) {
          setShowConfigureNotificationsCta(false);
        }
      }
    };

    void loadDeliverySettings();

    return () => {
      isMounted = false;
      window.removeEventListener(
        DELIVERY_SETTINGS_CHANGED_EVENT,
        handleDeliverySettingsChanged,
      );
    };
  }, [isAdmin]);

  const handleConfigureNotifications = () => {
    onClose();
    navigate("/dashboard?openDeliverySettings=1");
  };

  return (
    <aside className={`app-sidebar ${isOpen ? "open" : ""}`} aria-label="Sidebar navigation">
      <div className="nav-panel">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onClose}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>

      {!isAdmin && showConfigureNotificationsCta && (
        <section className="next-step">
          <p className="next-step-kicker">NEXT STEP</p>
          <h3>Enable live delivery</h3>
          <p>Turn on SMS + Email notifications so new leads arrive instantly.</p>
          <button type="button" onClick={handleConfigureNotifications}>
            Configure Notifications
          </button>
        </section>
      )}
    </aside>
  );
};

export default Sidebar;
