#Bytecode instructions
| Mnemonic | Opcode Name |  Exists in |  Count |
| :---- | :---- | :----- | -----: |
 | [iload_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iload_n) | [Load](jpamb/jvm/opcode.py?plain=1#L916) |  Arrays Dependent Loops Simple Tricky | 139 |
 | [iconst_i](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iconst_i) | [Push](jpamb/jvm/opcode.py?plain=1#L120) |  Arrays Dependent Loops Simple Tricky | 129 |
 | [if_cond](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.if_cond) | [Ifz](jpamb/jvm/opcode.py?plain=1#L1156) |  Arrays Dependent Loops Simple Tricky | 77 |
 | [dup](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.dup) | [Dup](jpamb/jvm/opcode.py?plain=1#L393) |  Arrays Loops Simple Tricky | 61 |
 | [return](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.return) | [Return](jpamb/jvm/opcode.py?plain=1#L1509) |  Arrays Calls Loops Tricky | 47 |
 | [if_icmp_cond](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.if_icmp_cond) | [If](jpamb/jvm/opcode.py?plain=1#L980) |  Arrays Tricky | 45 |
 | [ldc](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.ldc) | [Push](jpamb/jvm/opcode.py?plain=1#L120) |  Arrays | 42 |
 | [istore_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.istore_n) | [Store](jpamb/jvm/opcode.py?plain=1#L754) |  Arrays Loops Tricky | 42 |
 | [aload_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.aload_n) | [Load](jpamb/jvm/opcode.py?plain=1#L916) |  Arrays | 41 |
 | [getstatic](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.getstatic) | [Get](jpamb/jvm/opcode.py?plain=1#L1095) |  Arrays Loops Simple Tricky | 38 |
 | [new](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.new) | [New](jpamb/jvm/opcode.py?plain=1#L1351) |  Arrays Loops Simple Tricky | 38 |
 | [invokespecial](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.invokespecial) | [InvokeSpecial](jpamb/jvm/opcode.py?plain=1#L704) |  Arrays Loops Simple Tricky | 38 |
 | [athrow](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.athrow) | [Throw](jpamb/jvm/opcode.py?plain=1#L1390) |  Arrays Loops Simple Tricky | 38 |
 | [ireturn](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.ireturn) | [Return](jpamb/jvm/opcode.py?plain=1#L1509) |  Dependent Simple | 31 |
 | [idiv](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.idiv) | [Binary](jpamb/jvm/opcode.py?plain=1#L846) |  Arrays Dependent Simple Tricky | 30 |
 | [iastore](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iastore) | [ArrayStore](jpamb/jvm/opcode.py?plain=1#L428) |  Arrays | 28 |
 | [goto](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.goto) | [Goto](jpamb/jvm/opcode.py?plain=1#L1469) |  Arrays Loops Tricky | 20 |
 | [astore_n](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.astore_n) | [Store](jpamb/jvm/opcode.py?plain=1#L754) |  Arrays | 15 |
 | [caload](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.caload) | [ArrayLoad](jpamb/jvm/opcode.py?plain=1#L511) |  | 15 |
 | [arraylength](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.arraylength) | [ArrayLength](jpamb/jvm/opcode.py?plain=1#L562) |  Arrays | 12 |
 | [isub](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.isub) | [Binary](jpamb/jvm/opcode.py?plain=1#L846) |  Arrays | 11 |
 | [iload](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iload) | [Load](jpamb/jvm/opcode.py?plain=1#L916) |  Arrays | 11 |
 | [iadd](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iadd) | [Binary](jpamb/jvm/opcode.py?plain=1#L846) |  Arrays Loops Tricky | 10 |
 | [invokestatic](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.invokestatic) | [InvokeStatic](jpamb/jvm/opcode.py?plain=1#L631) |  Calls | 10 |
 | [iaload](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iaload) | [ArrayLoad](jpamb/jvm/opcode.py?plain=1#L511) |  Arrays | 9 |
 | [newarray](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.newarray) | [NewArray](jpamb/jvm/opcode.py?plain=1#L354) |  Arrays | 8 |
 | [iinc](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.iinc) | [Incr](jpamb/jvm/opcode.py?plain=1#L1427) |  | 8 |
 | [ineg](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.ineg) | [Negate](jpamb/jvm/opcode.py?plain=1#L329) |  | 6 |
 | [istore](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.istore) | [Store](jpamb/jvm/opcode.py?plain=1#L754) |  Arrays | 5 |
 | [aconst_null](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.aconst_null) | [Push](jpamb/jvm/opcode.py?plain=1#L120) |  | 4 |
 | [imul](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.imul) | [Binary](jpamb/jvm/opcode.py?plain=1#L846) |  Tricky | 3 |
 | [irem](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.irem) | [Binary](jpamb/jvm/opcode.py?plain=1#L846) |  Tricky | 2 |
 | [i2s](https://docs.oracle.com/javase/specs/jvms/se23/html/jvms-6.html#jvms-6.5.i2s) | [Cast](jpamb/jvm/opcode.py?plain=1#L477) |  Loops | 1 |
