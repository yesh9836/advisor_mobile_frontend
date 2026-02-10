import LicenseApproval from "@/components/admin/LicenseApproval";

const AdminDashboard = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-semibold text-[#0a1633]">Admin Console</h1>
        <p className="mt-1 text-base text-[#4c628a]">
          Review advisor license submissions and approve or reject pending requests.
        </p>
      </div>

      <LicenseApproval />
    </div>
  );
};

export default AdminDashboard;
