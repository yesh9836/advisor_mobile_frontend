import axios from "axios";
import { useCallback, useEffect, useState } from "react";

import { getPurchaseBalance, getPurchaseHistory } from "@/api/purchases";
import Card from "@/components/common/Card";
import LicenseForm from "@/components/license/LicenseForm";
import LicenseList from "@/components/license/LicenseList";
import { useAuth } from "@/context/AuthContext";
import type { PurchaseBalance, PurchaseOrderItem } from "@/types/purchase";
import { getApiErrorMessage } from "@/utils/api-error";
import { isRequestCanceled, useLatestRequest } from "@/utils/request-control";

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

const formatFulfillmentStatus = (
  fulfillmentStatus: PurchaseOrderItem["fulfillment_status"],
): string => {
  switch (fulfillmentStatus) {
    case "fulfilled":
      return "Fulfilled";
    case "partially_fulfilled":
      return "Partially fulfilled";
    case "pending_inventory":
      return "Pending inventory";
    case "pending":
      return "Payment pending";
    default:
      return "Not completed";
  }
};

const ProfilePage = () => {
  const { user } = useAuth();

  const [balance, setBalance] = useState<PurchaseBalance | null>(null);
  const [recentPurchases, setRecentPurchases] = useState<PurchaseOrderItem[]>([]);
  const [billingLoading, setBillingLoading] = useState(true);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [licensesRefreshKey, setLicensesRefreshKey] = useState(0);
  const { beginRequest, isLatestRequest } = useLatestRequest();

  const loadPurchaseSummary = useCallback(async () => {
    const { requestId, signal } = beginRequest();
    setBillingLoading(true);
    setBillingError(null);

    try {
      const [balanceResponse, historyResponse] = await Promise.all([
        getPurchaseBalance({ signal }),
        getPurchaseHistory(5, { signal }),
      ]);
      if (!isLatestRequest(requestId)) {
        return;
      }
      setBalance(balanceResponse);
      setRecentPurchases(historyResponse.items);
    } catch (error) {
      if (!isLatestRequest(requestId) || isRequestCanceled(error)) {
        return;
      }
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        setBalance(null);
        setRecentPurchases([]);
      } else {
        setBillingError(
          getApiErrorMessage(error, "Unable to load purchase summary."),
        );
      }
    } finally {
      if (isLatestRequest(requestId)) {
        setBillingLoading(false);
      }
    }
  }, [beginRequest, isLatestRequest]);

  useEffect(() => {
    void loadPurchaseSummary();
  }, [loadPurchaseSummary]);

  const latestCompletedPurchase =
    recentPurchases.find(
      (purchase) => String(purchase.status || "").toLowerCase() === "completed",
    ) ?? null;
  const pendingAutoDeliveryLeads = recentPurchases.reduce((total, purchase) => {
    if (
      purchase.fulfillment_status !== "partially_fulfilled"
      && purchase.fulfillment_status !== "pending_inventory"
    ) {
      return total;
    }
    return total + Math.max(purchase.unfulfilled_count, 0);
  }, 0);

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
              <p>
                <span className="font-semibold text-[#0a1633]">Pending auto-delivery leads:</span>{" "}
                {pendingAutoDeliveryLeads}
              </p>
              {latestCompletedPurchase && (
                <div className="space-y-1 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                  <p>
                    <span className="font-semibold text-[#0a1633]">Latest completed purchase:</span>{" "}
                    {latestCompletedPurchase.package_name ?? "Package"} on{" "}
                    {formatDate(latestCompletedPurchase.purchased_at)}
                  </p>
                  <p>
                    <span className="font-semibold text-[#0a1633]">Delivered now:</span>{" "}
                    {latestCompletedPurchase.assigned_count}/{latestCompletedPurchase.entitled_credits_total}
                  </p>
                  <p>
                    <span className="font-semibold text-[#0a1633]">Pending auto-delivery:</span>{" "}
                    {Math.max(latestCompletedPurchase.unfulfilled_count, 0)}
                  </p>
                  <p>
                    <span className="font-semibold text-[#0a1633]">Fulfillment:</span>{" "}
                    {formatFulfillmentStatus(latestCompletedPurchase.fulfillment_status)}
                  </p>
                </div>
              )}
              <p className="text-xs text-[#64748b]">
                New leads are assigned automatically when inventory is available in your licensed states.
              </p>
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
