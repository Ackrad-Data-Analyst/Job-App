import {NextRequest,NextResponse} from 'next/server';
import {timingSafeEqual} from 'node:crypto';
import {sign,sameOrigin,COOKIE} from '@/lib/session';
let used=false,failures=0;
export async function POST(request:NextRequest){
 if(!sameOrigin(request))return NextResponse.json({detail:'Invalid origin'},{status:403});
 try{const {code}=await request.json();const expected=process.env.CAREERPILOT_BOOTSTRAP_CODE;const deadline=Number(process.env.CAREERPILOT_BOOTSTRAP_DEADLINE||0);const a=Buffer.from(String(code||''));const b=Buffer.from(expected||'');
 if(used||failures>=10||Date.now()>deadline||!expected||a.length!==b.length||!timingSafeEqual(a,b)){failures++;return NextResponse.json({detail:'Unlock expired or already used. Stop and start CareerPilot again.'},{status:401});}
 used=true;const response=NextResponse.json({ok:true});const origin=new URL(process.env.APP_ORIGIN!);response.cookies.set(COOKIE,sign(),{httpOnly:true,sameSite:'strict',secure:origin.protocol==='https:'||!['127.0.0.1','localhost'].includes(origin.hostname),path:'/',maxAge:8*3600});return response;
 }catch{return NextResponse.json({detail:'Unable to unlock. Restart CareerPilot.'},{status:401});}
}
