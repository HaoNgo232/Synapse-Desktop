# **Phân tích Rủi ro Dây chuyền và Kế hoạch Refactor cho Synapse Desktop**

## **1. Những Điểm Rủi ro Nghiêm trọng về Lỗi Dây chuyền**

### **1.1. Hệ thống Tokenization - Rủi ro Cấp độ NGHIÊM TRỌNG**

**Vấn đề cốt lõi:**
Hệ thống đếm token hiện tại dựa trên global state và có nhiều lớp cache chồng chéo, tạo ra điểm lỗi nghiêm trọng khi có bất kỳ thay đổi nào.

**Các file liên quan:**
- `core/encoders.py` - Global state: `_encoder`, `_encoder_type`, `_claude_tokenizer`
- `core/tokenization/counter.py` - Default encoder config
- `services/encoder_registry.py` - Model configuration wrapper
- `services/token_display.py` - Service layer cache
- `components/file_tree_model.py` - UI layer cache

**Điểm dễ vỡ cụ thể:**
```python
# Khi thay đổi model trong UI
def _on_model_changed(self, model_id: str) -> None:
    reset_encoder()  # ← Global state reset
    model._token_cache.clear()  # ← Manual cache clear
    initialize_encoder()  # ← Reload encoder
```

**Tác động dây chuyền:**
- Thay đổi encoder logic → 15+ files phải update
- Race condition khi switch model → segfault hoặc token count sai
- Cache invalidation không đồng bộ → memory leak hoặc stale data

### **1.2. FileTreeModel - God Object với State phức tạp**

**Vấn đề:**
Class `FileTreeModel` (1200+ dòng code) quản lý quá nhiều concerns:
- Selection state management
- Token counting và caching
- Folder state caching  
- Search index integration
- Background worker coordination

**Điểm dễ vỡ:**
```python
def _select_node(self, node: TreeNode) -> None:
    self._select_all_recursive(node)  # ← Recursive operation
    self._remove_ancestors_from_selected(node)  # ← Side effects
    self._clear_folder_state_cache()  # ← Cache invalidation
    self._emit_parent_changes(node)  # ← Signal cascading
    self._emit_tree_checkstate_changed()  # ← UI update
```

**Tác động dây chuyền:**
- Thêm field mới vào `TreeNode` → 10+ methods cần update
- Thay đổi selection logic → token counting, UI display, prompt generation đều bị ảnh hưởng
- Performance issue khi tree lớn → UI freeze

### **1.3. Context View Copy Actions - Tight Coupling nghiêm trọng**

**Vấn đề:**
`views/context/_copy_actions.py` có 1000+ dòng code và phụ thuộc vào quá nhiều systems:

**Dependencies cascade:**
```
CopyActionsMixin → TokenCounter → Encoder → ModelConfig → Settings
                → SecurityCheck → SecretScanner → FileUtils
                → PromptGenerator → SmartContext → TreeSitter
                → GitUtils → Subprocess → SystemCommands
                → ClipboardUtils → SystemClipboard
```

**Điểm dễ vỡ:**
- Generation guard pattern phức tạp với `_copy_generation`, `_stale_workers`
- QRunnable lifecycle management có history của segfaults
- Cache fingerprinting phụ thuộc vào file mtime và content hash

### **1.4. Smart Context System - Cache và Tree-sitter complexity**

**Vấn đề:**
- `_RELATIONSHIPS_CACHE` global với MD5 hash keys
- Multiple parser strategies với shared base class
- Tree-sitter language loading và query execution

**Điểm dễ vỡ:**
```python
# core/smart_context/parser.py
def _build_relationships_section(file_path: str, content: str, tree=None):
    content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
    cached = _get_cached_relationships(file_path, content_hash)  # ← Global cache
    # ... complex parsing logic
```

**Tác động dây chuyền:**
- Thay đổi relationship format → cache invalidation → performance degradation
- Update tree-sitter queries → parsing results khác biệt → test failures
- Strategy changes → output format khác biệt → prompt generation sai

### **1.5. Settings Management - Scattered State**

**Vấn đề:**
Settings được phân tán ở nhiều nơi không có coordination:
- `services/settings_manager.py` - Core settings JSON
- `services/workspace_config.py` - Excluded patterns
- `services/session_state.py` - Workspace session
- `services/recent_folders.py` - Folder history

**Tác động dây chuyền:**
- Thêm setting mới → phải nhớ update đúng service
- Settings conflict → data inconsistency
- Migration logic phức tạp khi đổi format

## **2. Đánh giá Mức độ Ưu tiên**

### **Ưu tiên NGAY LẬP TỨC (Critical)**
1. **Token System Refactor** - Có race conditions thực sự ảnh hưởng UX
2. **Copy Actions Stabilization** - Đã có history segfaults từ git log

### **Ưu tiên CAO (High)**
3. **FileTreeModel Decomposition** - God object gây khó maintain
4. **Settings Unification** - Prevent data inconsistency

### **Ưu tiên TRUNG BÌNH (Medium)**
5. **Smart Context Cache Management** - Performance optimization
6. **View-Controller Separation** - Long-term maintainability

## **3. Kế hoạch Refactor Chi tiết**

### **Phase 1: Token System Stabilization (Tuần 1-2)**

**Mục tiêu:** Loại bỏ global state và race conditions trong tokenization

**Thiết kế TokenizationService:**
```python
# services/tokenization_service.py
class TokenizationService:
    def __init__(self, config_provider: IConfigProvider):
        self._config_provider = config_provider
        self._encoder_cache: Dict[str, Any] = {}
        self._token_cache = TokenCache()
        self._lock = threading.RLock()
    
    def count_tokens(self, text: str) -> int:
        model_id = self._config_provider.get_current_model()
        encoder = self._get_encoder(model_id)
        return len(encoder.encode(text))
    
    def count_tokens_batch(self, files: List[Path]) -> Dict[str, int]:
        # Centralized batch processing logic
        pass
```

**Migration Strategy:**
1. Tạo `TokenizationService` với interface tương thích
2. Update `core/token_counter.py` thành shim wrapper
3. Migrate từng consumer một cách tuần tự
4. Deprecate global functions sau khi hoàn thành

**Tests cần pass:**
- `tests/test_tokenization.py`
- `tests/test_token_counter.py`
- `tests/test_claude_tokenizer.py`

### **Phase 2: FileTreeModel Decomposition (Tuần 3-4)**

**Mục tiêu:** Tách concerns và giảm complexity

**Thiết kế Component Architecture:**
```python
# components/file_tree/managers/selection_manager.py
class SelectionManager:
    def __init__(self, event_bus: IEventBus):
        self._selected_paths: Set[str] = set()
        self._event_bus = event_bus
    
    def select_paths(self, paths: Set[str]) -> None:
        old_selection = self._selected_paths.copy()
        self._selected_paths.update(paths)
        self._event_bus.emit('selection_changed', {
            'added': paths - old_selection,
            'removed': old_selection - paths
        })

# components/file_tree/managers/token_manager.py
class TokenManager:
    def __init__(self, tokenization_service: TokenizationService):
        self._tokenization_service = tokenization_service
        self._token_counts: Dict[str, int] = {}
    
    def update_tokens_for_paths(self, paths: Set[str]) -> None:
        # Delegate to tokenization service
        pass
```

**Migration Strategy:**
1. Extract managers từ `FileTreeModel`
2. Implement event bus pattern cho communication
3. Update `FileTreeWidget` để sử dụng managers
4. Gradually migrate methods từ model sang managers

### **Phase 3: Copy Actions Refactor (Tuần 5-6)**

**Mục tiêu:** Command pattern và dependency injection

**Thiết kế Command System:**
```python
# views/context/commands/base.py
class CopyCommand(ABC):
    def __init__(self, context: CopyContext):
        self.context = context
        self.generation = context.current_generation
    
    @abstractmethod
    async def execute(self) -> CopyResult:
        pass
    
    def is_stale(self) -> bool:
        return self.generation != self.context.current_generation

# views/context/commands/copy_context_command.py
class CopyContextCommand(CopyCommand):
    async def execute(self) -> CopyResult:
        if self.is_stale():
            return CopyResult.cancelled()
        
        # Execute copy logic
        prompt = await self._generate_prompt()
        return CopyResult.success(prompt)
```

**Benefits:**
- Loại bỏ 80% code trong `_copy_actions.py`
- Dễ test từng command riêng biệt
- Generation guard được built-in vào pattern

### **Phase 4: Settings Unification (Tuần 7-8)**

**Mục tiêu:** Single source of truth cho configuration

**Thiết kế AppConfig Service:**
```python
# services/app_config.py
class AppConfig:
    def __init__(self):
        self._settings = self._load_unified_settings()
        self._observers: Dict[str, List[Callable]] = defaultdict(list)
    
    def get_model_config(self) -> ModelConfig:
        model_id = self._settings.get("model_id", DEFAULT_MODEL_ID)
        return get_model_by_id(model_id)
    
    def get_output_style(self) -> OutputStyle:
        style_id = self._settings.get("output_format", DEFAULT_OUTPUT_STYLE.value)
        return get_style_by_id(style_id)
    
    def subscribe_to_changes(self, key: str, callback: Callable) -> None:
        self._observers[key].append(callback)
```

## **4. Architectural Improvements**

### **4.1. Dependency Injection Pattern**

**Hiện tại:**
```python
# views/context_view_qt.py - Direct imports
from core.token_counter import count_tokens
from services.settings_manager import get_setting
```

**Sau refactor:**
```python
# views/context_view_qt.py - Injected dependencies
class ContextViewQt(QWidget):
    def __init__(self, 
                 tokenization_service: TokenizationService,
                 app_config: AppConfig,
                 workspace_service: WorkspaceService):
        self._tokenization = tokenization_service
        self._config = app_config
        self._workspace = workspace_service
```

### **4.2. Event-Driven Architecture**

**Thiết kế Event Bus:**
```python
# core/events/event_bus.py
class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type].append(handler)
    
    def emit(self, event_type: str, data: Any) -> None:
        for handler in self._handlers[event_type]:
            try:
                handler(data)
            except Exception as e:
                log_error(f"Event handler error: {e}")
```

**Benefits:**
- Giảm coupling giữa components
- Dễ dàng thêm features mới mà không sửa code cũ
- Built-in error handling

### **4.3. Generation Guard Pattern Standardization**

**Template cho mọi async operations:**
```python
# core/patterns/generation_guard.py
class GenerationGuardMixin:
    def __init__(self):
        self._current_generation = 0
        self._active_workers: Set[QRunnable] = set()
    
    def start_guarded_operation(self, worker: QRunnable) -> int:
        self._current_generation += 1
        worker.generation = self._current_generation
        self._active_workers.add(worker)
        return self._current_generation
    
    def is_current_generation(self, generation: int) -> bool:
        return generation == self._current_generation
    
    def cancel_stale_operations(self) -> None:
        self._current_generation += 1
        # Cleanup stale workers
```

## **5. Implementation Roadmap**

### **Week 1-2: Token System Foundation**
```bash
# Deliverables:
- services/tokenization_service.py (NEW)
- core/interfaces/tokenization.py (NEW) 
- Migration của core/token_counter.py
- Update 15+ callsites
- Integration tests

# Success Criteria:
✅ Không có global state trong encoders
✅ Model switch không race condition
✅ Existing tests pass
✅ Performance không giảm > 5%
```

### **Week 3-4: FileTree Decomposition**
```bash
# Deliverables:
- components/file_tree/managers/ (NEW package)
- selection_manager.py, token_manager.py, folder_manager.py
- Refactor FileTreeModel để sử dụng managers
- Event bus integration

# Success Criteria:
✅ Mỗi manager class < 300 lines
✅ Clear separation of concerns
✅ UI behavior không thay đổi
✅ Test coverage > 85%
```

### **Week 5-6: Copy Actions Refactor**
```bash
# Deliverables:
- views/context/commands/ (NEW package)
- Command pattern implementation
- Strategy pattern cho output formats
- Generation guard integration

# Success Criteria:
✅ _copy_actions.py giảm từ 1000 → 200 lines
✅ Thêm format mới chỉ cần 1 strategy class
✅ Generation guard prevents stale results
✅ Copy performance cải thiện 10%
```

### **Week 7-8: Settings Unification**
```bash
# Deliverables:
- services/app_config.py (NEW)
- Migration tất cả settings services
- Observer pattern cho settings changes
- Backward compatibility layer

# Success Criteria:
✅ Single source of truth cho settings
✅ Settings changes propagate tự động
✅ No breaking changes cho data files
✅ Settings validation built-in
```

## **6. Risk Mitigation Strategy**

### **6.1. Feature Flags**
```python
# config/feature_flags.py
REFACTOR_FLAGS = {
    "use_tokenization_service": False,
    "use_decomposed_tree_model": False,
    "use_command_copy_actions": False,
    "use_unified_settings": False,
}
```

### **6.2. Parallel Implementation**
- Implement new code song song với code cũ
- Sử dụng feature flags để switch
- Gradual rollout với monitoring
- Rollback plan cho mỗi phase

### **6.3. Testing Strategy**
```python
# tests/integration/test_refactor_compatibility.py
class TestRefactorCompatibility:
    """Ensure refactored code maintains exact same behavior"""
    
    def test_token_counting_results_identical(self):
        # Compare old vs new tokenization results
        pass
    
    def test_file_tree_selection_behavior_unchanged(self):
        # Verify selection logic works identically
        pass
```

## **7. Success Metrics**

### **Before Refactor (Hiện tại):**
- **Cyclomatic Complexity:** 15-30 (high risk)
- **Test Coverage:** ~45%
- **Average File Size:** 500+ lines
- **Module Coupling:** High (10+ dependencies per module)
- **Global State Count:** 15+ global variables
- **Race Condition Risk:** High (evident from git history)

### **After Refactor (Mục tiêu):**
- **Cyclomatic Complexity:** < 10 (low risk)
- **Test Coverage:** > 85%
- **Average File Size:** < 300 lines
- **Module Coupling:** Low (< 5 dependencies per module)
- **Global State Count:** 0 (all managed by services)
- **Race Condition Risk:** Minimal (generation guard pattern)
