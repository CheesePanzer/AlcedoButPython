# 当前局限性

本文档记录 Alcedo 当前已知但尚未实现或无法完整保证的行为。

## 聚合根版本与子实体变更

`AggregateRoot.version` 使用 SQLAlchemy 的 `version_id_col` 实现乐观并发控制。

当聚合根自身字段发生变化时，SQLAlchemy 会更新聚合根所在的数据表，并自动递增 `version`：

```text
version 1 -> version 2
```

对应的更新语句会带上原版本条件。若其他事务已经更新该记录，SQLAlchemy 会抛出 `StaleDataError`，框架将其映射为 HTTP 409。

但是，如果一次业务操作只增加、修改或删除聚合内的子实体，而聚合根自身没有字段变化，SQLAlchemy 可能只对关联表或子实体表执行 SQL：

```sql
INSERT INTO aggregate_children ...
DELETE FROM aggregate_children ...
```

此时聚合根数据表不会执行 `UPDATE`，因此当前存在以下限制：

- 聚合根的 `version` 不会因为子实体变化自动递增。
- 仅修改子实体时，不会自动触发聚合根的乐观版本检查。
- 两个事务并发修改同一聚合的不同或相同子实体时，不能只依赖根版本发现冲突。

当前建议在涉及聚合子实体写入的用例中，通过 Repository 的 `get_for_update()` 加载聚合根，使用数据库悲观锁串行化写操作：

```python
aggregate = await repository.get_for_update(aggregate_id)
aggregate.change_children(...)
```

该方案依赖数据库对 `SELECT ... FOR UPDATE` 的支持。PostgreSQL 和 MySQL 可以提供相应的行锁语义；SQLite 不提供等价的行级锁行为。

未来若需要保证“聚合内任意实体变化都递增根版本”，需要在 SQLAlchemy Session 的 flush 生命周期中检测子实体变化，并显式标记对应聚合根为已修改。当前框架尚未实现该机制。
