class SharedMemory:
    """Simple shared memory system for aisthesis, sophia and logos"""

    _instance = None

    def __init__(self):
        if SharedMemory._instance is None:
            self.experiences = (
                []
            )  # [{"context": str, "action": str, "outcome": str, "success": bool}]
            self.patterns = {}  # {"situation_type": [successful_actions]}
            self.failures = []  # [{"context": str, "action": str, "reason": str}]
            SharedMemory._instance = self

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls()

        return cls._instance

    def remember_success(self, context: str, action: str, outcome: str):
        """Remember successful experience"""
        self.experiences.append(
            {
                "context": context,
                "action": action,
                "outcome": outcome,
                "success": True,
            }
        )
        # Keep only last 50 experiences
        if len(self.experiences) > 50:
            self.experiences.pop(0)

    def remember_failure(self, context: str, action: str, reason: str):
        """Remember failure to avoid it"""
        self.failures.append({"context": context, "action": action, "reason": reason})
        if len(self.failures) > 20:
            self.failures.pop(0)

    def get_relevant_experience(self, current_context: str) -> str:
        """Get similar experiences (simple keyword matching)"""
        if not current_context:
            return ""

        keywords = current_context.lower().split()[:5]

        relevant = []
        for exp in self.experiences[-10:]:
            if any(word in exp["context"].lower() for word in keywords):
                relevant.append(f"• {exp['action']} → {exp['outcome']}")

        return "\n".join(relevant[-3:]) if relevant else ""

    def get_failure_warnings(self, current_context: str) -> str:
        """Get warnings about past failures"""
        if not current_context:
            return ""

        keywords = current_context.lower().split()[:5]

        warnings = []
        for failure in self.failures[-5:]:
            if any(word in failure["context"].lower() for word in keywords):
                warnings.append(f"⚠️ Avoid {failure['action']}: {failure['reason']}")

        return "\n".join(warnings) if warnings else ""
