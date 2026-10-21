import {
  codingStatusInfo,
  encounterReviewStatusInfo,
  suggestionReviewStatusInfo,
  validationStatusInfo,
} from "@/components/coding/status";

test("coding status labels", () => {
  expect(codingStatusInfo("completed").label).toBe("Coded");
  expect(codingStatusInfo("failed").label).toBe("Coding failed");
  expect(codingStatusInfo(null).label).toBe("Not coded");
});

test("encounter review status labels", () => {
  expect(encounterReviewStatusInfo("pending").label).toBe("Pending review");
  expect(encounterReviewStatusInfo("reviewed").label).toBe("Reviewed");
});

test("suggestion review status labels", () => {
  expect(suggestionReviewStatusInfo("approved").label).toBe("Approved");
  expect(suggestionReviewStatusInfo("rejected").label).toBe("Rejected");
  expect(suggestionReviewStatusInfo("corrected").label).toBe("Corrected");
});

test("validation status clearly distinguishes unavailable from valid", () => {
  expect(validationStatusInfo("valid").label).toBe("Validated");
  expect(validationStatusInfo("reference_data_unavailable").label).toBe("Reference data unavailable");
  expect(validationStatusInfo("unknown").label).toBe("Not in loaded dataset");
  expect(validationStatusInfo("date_invalid").label).toBe("Invalid for date of service");
  expect(validationStatusInfo(null).label).toBe("Not validated");
});
