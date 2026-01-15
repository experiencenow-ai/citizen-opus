# Instructions for Next Wake (Opus)

## Current Task
Repository reorganization and memory system deployment

## Status - Wake 1652
- ✅ Created memory repo: https://github.com/experiencenow-ai/memory
- ✅ Pushed REASONING_PRINCIPLES.md, WAKE_PROTOCOL.md, TASK_MANAGEMENT.md
- ✅ Removed REASONING_PRINCIPLES.md from protocols repo (DRY fix)
- ✅ Updated citizen-opus state_public.json
- ⏳ Need to push citizen-opus changes
- ⏳ Need to remove local REASONING_PRINCIPLES.md copies from citizen directories

## Context
- Repos are at /root/github_repos/
- Memory repo created and pushed via SSH (key: id_ed25519_github)
- ct wants clear separation: infra=code, protocols=governance, memory=continuity docs

## Next Steps
1. Push citizen-opus changes:
   ```
   cd /root/github_repos/citizen-opus
   git add -A && git commit -m "Update state wake 1652" && git push
   ```

2. Clean up local REASONING_PRINCIPLES.md duplicates:
   ```
   rm /root/claude/aria/REASONING_PRINCIPLES.md
   rm /root/claude/opus/REASONING_PRINCIPLES.md  
   rm /root/claude/mira/REASONING_PRINCIPLES.md
   ```

3. Update Aria and Mira to reference memory repo instead of local copies

4. Verify infra repo is code-only (check if any docs need moving)

## Blockers
- None currently

## Notes
- ct has limited time due to family situation - need to be autonomous
- The NEXT_WAKE.md pattern is critical for amnesiacs - lead by example
