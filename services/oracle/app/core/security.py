from typing import List

class SecurityPolicy:
    ROLE_LIMITS = {
        "admin": 5000,
        "manager": 2000,
        "attorney": 2000,
        "analyst": 1000,
        "engineer": 1000,
        "staff": 300,
        "viewer": 300
    }

    def get_row_limit_for_role(self, role: str) -> int:
        return self.ROLE_LIMITS.get(role, 300)

    def apply_masking(self, columns: List[str], rows: List[List], role: str) -> List[List]:
        if role == "admin":
            return rows
        
        mask_indices = []
        for i, col in enumerate(columns):
            if any(x in col.lower() for x in ["name", "address", "registration_no", "account"]):
                mask_indices.append(i)
                
        if not mask_indices:
            return rows
            
        masked_rows = []
        for row in rows:
            masked_row = list(row)
            for i in mask_indices:
                if masked_row[i] is not None:
                    masked_row[i] = "*** MASKED ***"
            masked_rows.append(masked_row)
        return masked_rows

security_policy = SecurityPolicy()
