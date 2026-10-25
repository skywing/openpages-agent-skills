# Object model snapshot: env `local` (https://aimpb.local:10111)

138 object types in environment; 8 detailed below.

## Finding (`Finding`, id 45)

- Parents: AuditProgram, AuditPhase, Engagement, Vendor, Workpaper
- Children: SOXDocument, SOXIssue, SOXExternalDocument, SOXSignature, ReviewComment, TPRRemediation

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `OPSS-Shared-Close:Ignore Trigger` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-Shared-Close:RdyToCls` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-Finding:Impact` | ENUM_TYPE |  |  | Significant, More Than Inconsequential, Inconsequential, Not Determined |
| `OPSS-Finding:MgmtActCompletion` | DATE_TYPE |  |  |  |
| `OPSS-Finding:MgmtExpCompletion` | DATE_TYPE |  |  |  |
| `OPSS-Finding:MgmtOwner` | STRING_TYPE |  |  |  |
| `OPSS-Finding:MgmtResp` | ENUM_TYPE |  |  | Agree, will create Action Plan, Agree, Action Plan not needed, Disagree, Require clarification |
| `OPSS-Finding:MgmtRespComment` | STRING_TYPE |  |  |  |
| `OPSS-Finding:MgmtRespStat` | ENUM_TYPE |  |  | Waiting for Response, Response Provided |
| `OPSS-Finding:MgmtSchedChgReason` | STRING_TYPE |  |  |  |
| `OPSS-Finding:MgmtSchedCompletion` | DATE_TYPE |  |  |  |
| `OPSS-Finding:Preparation Complete Date` | DATE_TYPE |  |  |  |
| `OPSS-Finding:Preparer` | STRING_TYPE |  |  |  |
| `OPSS-Finding:Priority` | ENUM_TYPE |  |  | High, Medium, Low, Not Determined |
| `OPSS-Finding:Recommendation` | STRING_TYPE |  |  |  |
| `OPSS-Finding:Reportable` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-Finding:Review Comments` | STRING_TYPE |  |  |  |
| `OPSS-Finding:Review Complete Date` | DATE_TYPE |  |  |  |
| `OPSS-Finding:Reviewer` | STRING_TYPE |  |  |  |
| `OPSS-Finding:Status` | ENUM_TYPE |  |  | Open, Closed |
| `TPR-Fnd:Source` | ENUM_TYPE |  |  | Vendor Attestation |

## Program (`Program`, id 15)

- Parents: SOXBusEntity
- Children: QuestionnaireTemplate, QuestionnaireAssessment, RiskEntity, Employee, Engagement, Model, SOXProcess, Resource, SOXSubprocess, Vendor, VendorSubsidiary, Subcontractor, LevelOne, LevelTwo

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `OPLC-Owners:AdditionalOwners` | STRING_TYPE |  |  |  |
| `OPLC-Owners:Approver` | STRING_TYPE |  |  |  |
| `OPLC-Owners:BusinessOwner` | STRING_TYPE |  |  |  |
| `OPLC-Owners:Control Attester` | STRING_TYPE |  |  |  |
| `OPLC-Owners:PrimaryOwner` | STRING_TYPE |  |  |  |
| `OPLC-Owners:Reviewer` | STRING_TYPE |  |  |  |
| `OPSS-Program:AssessmentDueDate` | DATE_TYPE |  |  |  |
| `OPSS-Program:LaunchProgram` | STRING_TYPE |  |  |  |
| `OPSS-Program:Lifecycle` | ENUM_TYPE |  |  | 2Stage, 3Stage, 4Stage |
| `OPSS-Program:Type` | ENUM_TYPE |  |  | Classification Questionnaire, Assessment Questionnaire |
| `OPSS-ProcShared:ProcessHistory` | STRING_TYPE |  |  |  |

## Questionnaire Assessment (`QuestionnaireAssessment`, id 14)

- Parents: Program, RiskEntity, Employee, Engagement, SOXProcess, Resource, SOXSubprocess, Vendor, VendorSubsidiary, Subcontractor, LevelOne
- Children: SOXDocument, QuestionnaireTemplate

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `OPSS-QAssessment:ComplianceScore` | INTEGER_TYPE |  |  |  |
| `OPSS-QAssessment:MaxRiskScore` | INTEGER_TYPE |  |  |  |
| `OPSS-QAssessment:Progress` | INTEGER_TYPE |  |  |  |
| `OPSS-QAssessment:RespQuest` | STRING_TYPE |  |  |  |
| `OPSS-QAssessment:RiskScore` | INTEGER_TYPE |  |  |  |
| `OPSS-QAssessment:Score` | INTEGER_TYPE |  |  |  |
| `OPLC-QAssessment:LCName` | ENUM_TYPE |  |  | 2Stage, 3Stage, 4Stage |
| `OPLC-QAssessment:LCStage` | ENUM_TYPE |  |  | 2Stage-Info, 2Stage-Close, 3Stage-Info, 3Stage-Review, 3Stage-Close, 4Stage-Info, 4Stage-Review, 4Stage-Approval, 4Stage-Close |
| `OPLC-QAssessment:LCStatus` | ENUM_TYPE |  |  | Complete, In Review, Rejected, In Approval, Review Rejected, Approved, Approval Rejected |
| `OPLC-QAssessment:LCTransition` | ENUM_TYPE |  |  | 2Stage-Info-Submit, 3Stage-Info-Submit, 3Stage-Review-Approve, 3Stage-Review-Reject, 4Stage-Info-Submit, 4Stage-Review-Approval, 4Stage-Review-Reject, 4Stage-Approval-Approve, 4Stage-Approval-Reject |
| `OPLC-Std:LCAssignee` | STRING_TYPE |  |  |  |
| `OPLC-Std:LCComment` | STRING_TYPE |  |  |  |
| `OPLC-Std:LCDueDate` | DATE_TYPE |  |  |  |
| `OPLC-Std:LCInReview` | BOOLEAN_TYPE |  |  |  |
| `OPLC-Std:LCReadOnly` | BOOLEAN_TYPE |  |  |  |
| `OPLC-Std:LCUpdateAssignee` | ENUM_TYPE |  |  | Yes |

## Questionnaire Template (`QuestionnaireTemplate`, id 10)

- Parents: SOXBusEntity, QuestionnaireAssessment, Program
- Children: SectionTemplate

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `OPSS-Qtemp:CompletionRequired` | BOOLEAN_TYPE |  |  |  |
| `OPSS-Qtemp:Scoring` | ENUM_TYPE |  |  | Simple, Weight Average |
| `OPSS-Qtemp:Type` | ENUM_TYPE |  |  | Classification Questionnaire, Assessment Questionnaire |
| `OPSS-Qtemp-Shared:Metadata` | LARGE_STRING_TYPE |  |  |  |
| `OPSS-Qtemp-Shared:Order` | INTEGER_TYPE |  |  |  |
| `OPSS-Qtemp-Shared:Rationale` | STRING_TYPE |  |  |  |
| `OPSS-Qtemp-Shared:Reference` | STRING_TYPE |  |  |  |
| `OPSS-Qtemp-Shared:ReportID` | STRING_TYPE |  |  |  |
| `OPSS-Qtemp-Shared:Title` | STRING_TYPE |  |  |  |
| `OPSS-Qtemp-Shared:Weight` | INTEGER_TYPE |  |  |  |
| `OPSS-Qtemp-Config:EnableAutoNumbering` | BOOLEAN_TYPE |  |  |  |
| `OPSS-Qtemp-Config:EnableTitles` | BOOLEAN_TYPE |  |  |  |
| `OPSS-Qtemp-Config:EnableWeightScore` | BOOLEAN_TYPE |  |  |  |
| `OPSS-Qtemp-Config:QuestionnaireDepth` | INTEGER_TYPE |  |  |  |
| `OPSS-Qtemp-Config:Required` | BOOLEAN_TYPE |  |  |  |
| `OPLC-Owners:AdditionalOwners` | STRING_TYPE |  |  |  |
| `OPLC-Owners:Approver` | STRING_TYPE |  |  |  |
| `OPLC-Owners:BusinessOwner` | STRING_TYPE |  |  |  |
| `OPLC-Owners:Control Attester` | STRING_TYPE |  |  |  |
| `OPLC-Owners:PrimaryOwner` | STRING_TYPE |  |  |  |
| `OPLC-Owners:Reviewer` | STRING_TYPE |  |  |  |

## Milestone (`TPRMilestone`, id 162)

- Parents: TPRRemediation
- Children: -

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `TPR-Ms:Due Date` | DATE_TYPE | Y |  |  |
| `TPR-Ms:Percent Complete` | INTEGER_TYPE |  |  |  |
| `TPR-Ms:Status` | ENUM_TYPE | Y |  | Not Started, In Progress, Done |

## Remediation (`TPRRemediation`, id 161)

- Parents: Finding
- Children: TPRMilestone

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `TPR-Rem:Estimated Cost` | CURRENCY_TYPE |  |  |  |
| `TPR-Rem:Open Milestones` | INTEGER_TYPE |  |  |  |
| `TPR-Rem:Plan Summary` | MEDIUM_STRING_TYPE |  |  |  |
| `TPR-Rem:Remediation Owner` | STRING_TYPE | Y |  |  |
| `TPR-Rem:Severity` | ENUM_TYPE | Y |  | Low, Medium, High, Critical |
| `TPR-Rem:Status` | ENUM_TYPE | Y |  | Draft, In Review, Approved, Closed |
| `TPR-Rem:Target Date` | DATE_TYPE | Y |  |  |
| `TPR-Rem:Total Milestones` | INTEGER_TYPE |  |  |  |
| `TPR-Rem:Vendor Confirmed` | BOOLEAN_TYPE |  |  |  |

## Vendor (`Vendor`, id 102)

- Parents: SOXBusEntity, Program, SOXProcess, RiskAssessment, SOXSubprocess, Location
- Children: SOXDocument, SOXIssue, SOXExternalDocument, SOXSignature, QuestionnaireAssessment, Contract, Engagement, Finding, Incident, KeyRiskIndicator, Waiver, BCBusinessImpactAnalysis, BCEvent, VendorSubsidiary, Subcontractor

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `OPSS-CIA:Availability` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-CIA:Confidentiality` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-CIA:Criticality` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-CIA:Integrity` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-VRM:Additional Details` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Address` | STRING_TYPE |  |  |  |
| `OPSS-VRM:BCM Contact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Business Unit Owner` | STRING_TYPE |  |  |  |
| `OPSS-VRM:City` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Comments` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Contract Owner` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Employees` | ENUM_TYPE |  |  | <100, 100-1000, >1000 |
| `OPSS-VRM:Eval Date` | DATE_TYPE |  |  |  |
| `OPSS-VRM:Global` | ENUM_TYPE |  |  | International, Domestic |
| `OPSS-VRM:Headquarters` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Info Sec Contact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Main Website` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Previous Eval Date` | DATE_TYPE |  |  |  |
| `OPSS-VRM:Previous RR` | ENUM_TYPE |  |  | High, Medium, Low |
| `OPSS-VRM:Previous RR Justification` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Public Company` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-VRM:QuestContact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Risk Rating` | ENUM_TYPE |  |  | High, Medium, Low |
| `OPSS-VRM:Risk Rating Justification` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Services Provided` | MULTI_VALUE_ENUM |  |  | Default |
| `OPSS-VRM:State` | ENUM_TYPE |  |  | AL, AK, AS, AZ, AR, CA, CO, CT, DE, DC, FM, FL, GA, GU, HI, ID, IL, IN, IA, KS, KY, LA, ME, MH, MD, MA, MI, MN, MS, MO, MT, NE, NV, NH, NJ, NM, NY, NC, ND, MP, OH, OK, OR, PW, PA, PR, RI, SC, SD, TN,  |
| `OPSS-VRM:Strategic Vendor` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-VRM:VContactemail` | STRING_TYPE |  |  |  |
| `OPSS-VRM:VContactPhone` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Vendor Owner` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Vendor Owner Assigned` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-VRM:Vendor Primary Contact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Vendor Status` | ENUM_TYPE |  |  | New, Due Diligence, Review In Progress, Ongoing Negotiations, Approved, Rejected, On-boarding, Inactive, Terminated |
| `OPSS-VRM:Zip` | STRING_TYPE |  |  |  |
| `BCM-Vendor:BCMAssess` | STRING_TYPE |  |  |  |
| `BCM-Vendor:Impact Score` | INTEGER_TYPE |  |  |  |
| `BCM-Vendor:Impact Tier` | ENUM_TYPE |  |  | Tier 1, Tier 2, Tier 3, Tier 4 |
| `BCM-Vendor:ImpTolBreachStatus` | ENUM_TYPE |  |  | Red, Yellow, Green, Not Applicable |
| `BCM-Vendor:Maximum Acceptable Outage` | ENUM_TYPE |  |  | Less than 24 hours, 1-3 days, 3-7 days, 1 week or more |
| `BCM-Vendor:ProcessRPO` | FLOAT_TYPE |  |  |  |
| `BCM-Vendor:ProcessRTO` | FLOAT_TYPE |  |  |  |
| `BCM-Vendor:Recovery Point` | FLOAT_TYPE |  |  |  |
| `BCM-Vendor:Recovery Time` | FLOAT_TYPE |  |  |  |
| `BCM-Vendor:RPO Alignment Warning` | ENUM_TYPE |  |  | Warning |
| `BCM-Vendor:RTO Alignment Warning` | ENUM_TYPE |  |  | Warning |
| `BCM-Vendor:VendorRPO` | FLOAT_TYPE |  |  |  |
| `BCM-Vendor:VendorRTO` | FLOAT_TYPE |  |  |  |

## Vendor Subsidiary (`VendorSubsidiary`, id 128)

- Parents: SOXBusEntity, Program, SOXProcess, RiskAssessment, SOXSubprocess, Vendor, Location
- Children: SOXDocument, SOXIssue, SOXExternalDocument, SOXSignature, QuestionnaireAssessment, Contract, Engagement, Incident, KeyRiskIndicator, Waiver, BCEvent, Subcontractor

| Field | Data type | Req | Computed | Enum values |
|---|---|---|---|---|
| `Resource ID` | ID_TYPE | Y |  |  |
| `Comment` | STRING_TYPE |  |  |  |
| `Created By` | INTEGER_TYPE | Y |  |  |
| `Creation Date` | DATE_TYPE | Y |  |  |
| `Description` | STRING_TYPE |  |  |  |
| `Last Modification Date` | DATE_TYPE | Y |  |  |
| `Last Modified By` | INTEGER_TYPE | Y |  |  |
| `Location` | STRING_TYPE | Y |  |  |
| `Name` | STRING_TYPE | Y |  |  |
| `Orphan` | STRING_TYPE |  |  |  |
| `Title` | STRING_TYPE |  |  |  |
| `OPSS-CIA:Availability` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-CIA:Confidentiality` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-CIA:Criticality` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-CIA:Integrity` | ENUM_TYPE |  |  | High, Medium, Low, Not Available |
| `OPSS-VRM:Additional Details` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Address` | STRING_TYPE |  |  |  |
| `OPSS-VRM:BCM Contact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Business Unit Owner` | STRING_TYPE |  |  |  |
| `OPSS-VRM:City` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Comments` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Contract Owner` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Employees` | ENUM_TYPE |  |  | <100, 100-1000, >1000 |
| `OPSS-VRM:Eval Date` | DATE_TYPE |  |  |  |
| `OPSS-VRM:Global` | ENUM_TYPE |  |  | International, Domestic |
| `OPSS-VRM:Headquarters` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Info Sec Contact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Main Website` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Previous Eval Date` | DATE_TYPE |  |  |  |
| `OPSS-VRM:Previous RR` | ENUM_TYPE |  |  | High, Medium, Low |
| `OPSS-VRM:Previous RR Justification` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Public Company` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-VRM:QuestContact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Risk Rating` | ENUM_TYPE |  |  | High, Medium, Low |
| `OPSS-VRM:Risk Rating Justification` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Services Provided` | MULTI_VALUE_ENUM |  |  | Default |
| `OPSS-VRM:State` | ENUM_TYPE |  |  | AL, AK, AS, AZ, AR, CA, CO, CT, DE, DC, FM, FL, GA, GU, HI, ID, IL, IN, IA, KS, KY, LA, ME, MH, MD, MA, MI, MN, MS, MO, MT, NE, NV, NH, NJ, NM, NY, NC, ND, MP, OH, OK, OR, PW, PA, PR, RI, SC, SD, TN,  |
| `OPSS-VRM:Strategic Vendor` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-VRM:VContactemail` | STRING_TYPE |  |  |  |
| `OPSS-VRM:VContactPhone` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Vendor Owner` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Vendor Owner Assigned` | ENUM_TYPE |  |  | Yes, No |
| `OPSS-VRM:Vendor Primary Contact` | STRING_TYPE |  |  |  |
| `OPSS-VRM:Vendor Status` | ENUM_TYPE |  |  | New, Due Diligence, Review In Progress, Ongoing Negotiations, Approved, Rejected, On-boarding, Inactive, Terminated |
| `OPSS-VRM:Zip` | STRING_TYPE |  |  |  |
| `TPRM-Vendor Subsidiary:Strategic Vendor Subsidiary` | ENUM_TYPE |  |  | Yes, No |
| `TPRM-Vendor Subsidiary:Vendor Subsidiary Contact Email` | STRING_TYPE |  |  |  |
| `TPRM-Vendor Subsidiary:Vendor Subsidiary Contact Phone` | STRING_TYPE |  |  |  |
| `TPRM-Vendor Subsidiary:Vendor Subsidiary Owner` | STRING_TYPE |  |  |  |
| `TPRM-Vendor Subsidiary:Vendor Subsidiary Owner Assigned` | ENUM_TYPE |  |  | Yes, No |
| `TPRM-Vendor Subsidiary:Vendor Subsidiary Primary Contact` | STRING_TYPE |  |  |  |
| `TPRM-Vendor Subsidiary:Vendor Subsidiary Status` | ENUM_TYPE |  |  | New, Due Diligence, Review in Progress, Ongoing Negotiations, Approved, Rejected, On-boarding, Inactive, Terminated |

# Workflows

## Questionnaire Assessment Workflow (id 65, v3, published) on `QuestionnaireAssessment`
- **Closed** (end): -
- **Start** (start): Start -> Information Gathering
- **Information Gathering** (node): Submit for Review -> Review; Submit and Close -> Closed
- **Review** (node): Submit for Approval -> Approval; Approve and Close -> Closed; Reject -> Information Gathering
- **Approval** (node): Approve and Close -> Closed; Reject -> Review

## Sys-Workflow-Finding (id 81, v2, published) on `Finding`
- **Start** (start): Start Finding Preparation -> Finding Preparation
- **Finding Preparation** (node): Send for Audit Review -> Review by Audit
- **Complete** (end): -
- **Review Management Response** (node): Ready to Close -> Complete; Reject -> Finding Preparation
- **Management Response** (node): Review Response from Management -> Review Management Response; Reject -> Finding Preparation
- **Review by Audit** (node): Send for Management Response -> Management Response; Rejected -> Finding Preparation

## TPR Remediation Lifecycle (id 121, v10, published) on `TPRRemediation`
- **Start** (start): Begin -> Draft
- **Draft** (node): Submit -> Review
- **Review** (node): Approve -> Approved; Rework -> Draft
- **Approved** (node): Close -> End
- **End** (end): -

## Vendor Assessment (id 85, v1, published) on `Vendor`
- **Review Assessment** (node): Approve Assessment -> Approve Assessment; Reject Responses -> Reject Assessment
- **Approve Assessment** (node): Create Issues -> Create Vendor Issues; End -> End
- **End** (end): -
- **Create Vendor Issues** (node): Close -> End
- **Reject Assessment** (node): Send Back to Vendor -> Conduct Vendor Assessment
- **Start** (start): Identify Vendor -> Identify Vendor
- **Identify Vendor** (node): Choose Questionnaire -> Identify Questionnaire
- **Identify Questionnaire** (node): Review Questions -> Review Questionnaire
- **Review Questionnaire** (node): Send to Vendor -> Conduct Vendor Assessment
- **Conduct Vendor Assessment** (node): Review Responses -> Review Assessment

## Vendor Due Diligence (id 87, v1, published) on `Vendor`
- **Review Vendor Information** (node): Conduct Due Diligence -> Conduct Due Diligence
- **Conduct Due Diligence** (node): Final Review -> Final Review
- **End** (end): -
- **Reject Vendor** (end): -
- **Final Review** (node): Approve -> End; Reject -> Reject Vendor
- **Start** (start): Gather Vendor Information -> Gather Vendor Information
- **Gather Vendor Information** (node): Review -> Review Vendor Information

## Vendor Onboarding (id 90, v1, published) on `Vendor`
- **Start** (start): Review -> Review Vendor Information
- **Review Vendor Information** (node): Input -> Conduct Due Diligence
- **Conduct Due Diligence** (node): Assign -> Perform Contracting Process
- **Perform Contracting Process** (node): Assign Business Owner -> Assign Vendor Manager
- **Final Review** (node): End -> End
- **End** (end): -
- **Assign Vendor Manager** (node): Assign Controls to Vendor Tasks -> Assign Controls
- **Assign Controls** (node): Assign KRIs to Vendor Tasks -> Assign KRIs
- **Assign KRIs** (node): Schedule Assessment Frequency -> Final Review

## Vendor Selection (id 91, v1, published) on `Vendor`
- **Start** (start): Identify Vendor Responsibilities -> Identify Vendor Responsibilities
- **Identify Vendor Responsibilities** (node): Draft RFI -> Create RFI
- **Create RFI** (node): Gather List of Vendors -> Identify List of Vendors
- **Identify List of Vendors** (node): RFI Process -> Gather RFI Questions
- **Gather RFI Questions** (node): Use Vendor Due Diligence Workflow -> Respond to RFI Questions
- **Respond to RFI Questions** (node): Select Vendor -> Select Vendor
- **Select Vendor** (end): -

## Vendor Termination (id 92, v1, published) on `Vendor`
- **Identify Vendor for Termination** (node): Select Replacement Vendor -> Identify Replacement Vendor; Confirm Terminated Status -> Confirm Vendor Status
- **Confirm Vendor Status** (node): Vendor Manager Completes Checklist -> Perform Vendor Termination Checklist
- **Identify Replacement Vendor** (node): Change Vendor Status -> Confirm Vendor Status
- **Perform Vendor Termination Checklist** (node): Send Termination Review -> Termination Notice
- **Termination Notice** (node): Confirm -> Confirm Termination
- **Confirm Termination** (node): End -> End
- **End** (end): -
- **Start** (start): Identify -> Identify Vendor for Termination
