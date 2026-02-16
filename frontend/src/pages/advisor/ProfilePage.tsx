import axios from "axios";
import { useCallback, useEffect, useState } from "react";

import { getPurchaseBalance, getPurchaseHistory } from "@/api/purchases";
import Card from "@/components/common/Card";
import LicenseForm from "@/components/license/LicenseForm";
import LicenseList from "@/components/license/LicenseList";
import { useAuth } from "@/context/AuthContext";
import type { PurchaseBalance, PurchaseOrderItem } from "@/types/purchase";
import { getApiErrorMessage } from "@/utils/api-error";

const formatDate = (value: string | null | undefined): string => {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const ProfilePage = () => {
  const { user } = useAuth();

  const [balance, setBalance] = useState<PurchaseBalance | null>(null);
  const [recentPurchases, setRecentPurchases] = useState<PurchaseOrderItem[]>([]);
  const [billingLoading, setBillingLoading] = useState(true);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [licensesRefreshKey, setLicensesRefreshKey] = useState(0);

  const loadPurchaseSummary = useCallback(async () => {
    setBillingLoading(true);
    setBillingError(null);

    try {
      const [balanceResponse, historyResponse] = await Promise.all([
        getPurchaseBalance(),
        getPurchaseHistory(5),
      ]);
      setBalance(balanceResponse);
      setRecentPurchases(historyResponse.items);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        setBalance(null);
        setRecentPurchases([]);
      } else {
        setBillingError(
          getApiErrorMessage(error, "Unable to load purchase summary."),
        );
      }
    } finally {
      setBillingLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPurchaseSummary();
  }, [loadPurchaseSummary]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-semibold text-[#0a1633]">
          Advisor Profile
        </h1>
        <p className="mt-1 text-base text-[#4c628a]">
          Manage account details, licenses, purchases, and credits.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="User Info">
          <div className="space-y-2 text-sm text-[#4c628a]">
            <p>
              <span className="font-semibold text-[#0a1633]">Name:</span>{" "}
              {user?.name ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-[#0a1633]">Email:</span>{" "}
              {user?.email ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-[#0a1633]">Phone:</span>{" "}
              {user?.phone ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-[#0a1633]">Role:</span>{" "}
              {user?.role ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-[#0a1633]">Joined:</span>{" "}
              {formatDate(user?.created_at)}
            </p>
          </div>
        </Card>

        <Card title="Credits & Purchases">
          {billingLoading ? (
            <p className="text-sm text-[#4c628a]">Loading purchase summary...</p>
          ) : billingError ? (
            <p className="text-sm text-[#8a1d1d]">{billingError}</p>
          ) : balance ? (
            <div className="space-y-2 text-sm text-[#4c628a]">
              <p>
                <span className="font-semibold text-[#0a1633]">Remaining credits:</span>{" "}
                {balance.remaining_credits}
              </p>
              <p>
                <span className="font-semibold text-[#0a1633]">Total credits purchased:</span>{" "}
                {balance.total_credits}
              </p>
              <p>
                <span className="font-semibold text-[#0a1633]">Completed purchases:</span>{" "}
                {balance.completed_purchases}
              </p>
              {recentPurchases.length > 0 && (
                <p>
                  <span className="font-semibold text-[#0a1633]">Latest purchase:</span>{" "}
                  {recentPurchases[0].package_name ?? "Package"} on{" "}
                  {formatDate(recentPurchases[0].purchased_at)}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-[#4c628a]">
              No completed purchases found.
            </p>
          )}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr,1.3fr]">
        <LicenseForm
          onSubmitted={() => {
            setLicensesRefreshKey((previous) => previous + 1);
            void loadPurchaseSummary();
          }}
        />
        <LicenseList refreshKey={licensesRefreshKey} />
      </div>
    </div>
  );
};

export default ProfilePage;
