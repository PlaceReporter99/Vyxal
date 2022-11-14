package vyxal

import vyxal.impls.Elements

object Interpreter {
  def execute(code: String)(using ctx: Context): Unit = {
    VyxalParser.parse(code) match {
      case Right(ast) =>
        println(ast)
        execute(ast)
        // todo implicit output according to settings
        if (!ctx.isStackEmpty) {
          println(ctx.peek)
        }
      case Left(error) =>
        println(s"Error while executing $code: $error")
        ???
    }
  }

  def execute(ast: AST)(using ctx: Context): Unit = {
    ast match {
      case AST.Number(value) => ctx.push(value)
      case AST.Str(value)    => ctx.push(value)
      case AST.Lst(elems) =>
        val list = collection.mutable.ListBuffer.empty[VAny]
        for (elem <- elems) {
          execute(elem)
          list += ctx.pop()
        }
        ctx.push(VList(list.toList*))
      case AST.Command(cmd) =>
        Elements.elements.get(cmd) match {
          case Some(elem) => elem.impl()
          case None       => throw RuntimeException(s"No such command: '$cmd'")
        }
      case AST.Group(elems) =>
        elems.foreach { elem => Interpreter.execute(elem) }
      case AST.Modified(fn) => fn()
      case AST.If(thenBody, elseBody) =>
        if (MiscHelpers.boolify(ctx.pop())) {
          execute(thenBody)
        } else if (elseBody.nonEmpty) {
          execute(elseBody.get)
        }
      case AST.While(None, body) =>
        val loopCtx = ctx.makeChild()
        loopCtx.contextVar = ctx.settings.rangeStart
        while (true) {
          execute(body)(using loopCtx)
          loopCtx.contextVar = loopCtx.contextVar.asInstanceOf[VNum] + 1
        }
      case AST.While(Some(cond), body) =>
        execute(cond)
        given loopCtx: Context = ctx.makeChild()
        loopCtx.contextVar = ctx.settings.rangeStart
        while (MiscHelpers.boolify(ctx.pop())) {
          execute(body)
          execute(cond)
          loopCtx.contextVar = loopCtx.contextVar.asInstanceOf[VNum] + 1
        }

      case AST.For(None, body) =>
        val iterable = ListHelpers.makeIterable(ctx.pop())(using ctx)
        given loopCtx: Context = ctx.makeChild()
        for (elem <- iterable) {
          loopCtx.contextVar = elem
          execute(body)(using loopCtx)
        }

      case AST.For(Some(name), body) =>
        println(name)
        val iterable = ListHelpers.makeIterable(ctx.pop())(using ctx)
        given loopCtx: Context = ctx.makeChild()
        for (elem <- iterable) {
          loopCtx.setVar(name, elem)
          loopCtx.contextVar = elem
          execute(body)(using loopCtx)
        }

      case lam: AST.Lambda      => ctx.push(VFun.fromLambda(lam))
      case AST.FnDef(name, lam) => ctx.setVar(name, VFun.fromLambda(lam))
      case AST.GetVar(name)     => ctx.push(ctx.getVar(name))
      case AST.SetVar(name)     => ctx.setVar(name, ctx.pop())
      case AST.ExecuteFn =>
        ctx.pop() match {
          case fn: VFun => executeFn(fn).foreach(ctx.push(_))
          case _        => ???
        }
      case _ => throw NotImplementedError(s"$ast not implemented")
    }
  }

  /** Execute a function and return what was on the top of the stack, if there
    * was anything
    */
  def executeFn(fn: VFun)(using ctx: Context): Option[VAny] = {
    val VFun(impl, arity, params, origCtx) = fn
    given fnCtx: Context = Context.makeFnCtx(origCtx, ctx, arity, params)

    impl()

    Option.when(!fnCtx.isStackEmpty)(fnCtx.pop())
  }
}
