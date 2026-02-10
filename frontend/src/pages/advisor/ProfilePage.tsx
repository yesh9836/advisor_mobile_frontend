import axios from "axios";
import { useCallback, useEffect, useState } from "react";

import { getCurrentSubscription } from "@/api/subscriptions";
import Card from "@/components/common/Card";
import LicenseForm from "@/components/license/LicenseForm";
import LicenseList from "@/components/license/LicenseList";
import { useAuth } from "@/context/AuthContext";
import type { Subscription } from "@/types/subscription";

interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string }>;
}

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item.msg ?? "Validation error").join(", ");
    }
    return error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
};

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

  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(true);
  const [subscriptionError, setSubscriptionError] = useState<string | null>(
    null,
  );
  const [licensesRefreshKey, setLicensesRefreshKey] = useState(0);

  const loadSubscription = useCallback(async () => {
    setSubscriptionLoading(true);
    setSubscriptionError(null);

    try {
      const current = await getCurrentSubscription();
      setSubscription(current);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        setSubscription(null);
      } else {
        setSubscriptionError(
          getErrorMessage(error, "Unable to load subscription status."),
        );
      }
    } finally {
      setSubscriptionLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSubscription();
  }, [loadSubscription]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-semibold text-[#0a1633]">
          Advisor Profile
        </h1>
        <p className="mt-1 text-base text-[#4c628a]">
          Manage account details, licenses, and subscription status.
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

        <Card title="Subscription Status">
          {subscriptionLoading ? (
            <p className="text-sm text-[#4c628a]">Loading subscription...</p>
          ) : subscriptionError ? (
            <p className="text-sm text-[#8a1d1d]">{subscriptionError}</p>
          ) : subscription ? (
            <div className="space-y-2 text-sm text-[#4c628a]">
              <p>
                <span className="font-semibold text-[#0a1633]">Plan:</span>{" "}
                {subscription.plan.name}
              </p>
              <p className="capitalize">
                <span className="font-semibold text-[#0a1633]">Status:</span>{" "}
                {subscription.status}
              </p>
              <p>
                <span className="font-semibold text-[#0a1633]">
                  Billing period:
                </span>{" "}
                {formatDate(subscription.current_period_start)} -{" "}
                {formatDate(subscription.current_period_end)}
              </p>
            </div>
          ) : (
            <p className="text-sm text-[#4c628a]">
              No active subscription found.
            </p>
          )}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr,1.3fr]">
        <LicenseForm
          onSubmitted={() => {
            setLicensesRefreshKey((previous) => previous + 1);
            void loadSubscription();
          }}
        />
        <LicenseList refreshKey={licensesRefreshKey} />
      </div>
    </div>
  );
};

export default ProfilePage;
