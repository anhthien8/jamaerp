import JamaLoader from '@/components/ui/JamaLoader';

// Next bọc mọi trang trong <Suspense fallback={<Loading/>}> — chuyển trang hiện
// logo ngay trong vùng nội dung, thanh menu bên trái vẫn đứng yên.
export default function Loading() {
  return <JamaLoader />;
}
