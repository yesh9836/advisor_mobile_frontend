import LicenseApproval from "@/components/admin/LicenseApproval";

const LicenseReviewsPage = () => {
  return (
    <div className="page">
      <div>
        <h1>Admin • License Reviews</h1>
        <p className="page-subtitle">
          Review advisor license submissions and track processed decisions.
        </p>
      </div>

      <LicenseApproval />
    </div>
  );
};

export default LicenseReviewsPage;
